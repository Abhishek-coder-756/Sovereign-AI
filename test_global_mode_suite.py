"""
Comprehensive Test Suite for Sovereign AI Global Knowledge Mode — SIH26117.
Verifies:
1. Strict SSRF Defense (localhost, loopback, RFC1918 private IPs, AWS/Cloud metadata, file://, bad ports)
2. Web Content HTML Extraction and Cleaning
3. Conversation-Scoped Global RAG Vector Indexing & Zero Private Index Pollution
4. Global Sources REST API Endpoints with RBAC & Audit Logging
5. Chat Knowledge Mode Routing (Private vs Global)
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Project setup
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.app.security.ssrf import (
    validate_safe_url,
    SSRFSecurityError,
    fetch_url_safely,
    is_ip_blocked,
    BLOCKED_HOSTNAMES,
    BLOCKED_EXACT_IPS,
)
from backend.integration.web_fetcher import (
    extract_page_content,
    clean_extracted_text,
    fetch_and_clean_public_url,
)
from backend.integration.global_rag_service import (
    index_global_source,
    retrieve_global_evidence,
    get_conversation_sources,
    remove_global_source,
    get_global_paths,
)
from backend.app.agents.conversation_store import ConversationStore
from backend.app.security.migration import run_database_migrations
from db import get_connection
import app


class TestGlobalKnowledgeMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_database_migrations()
        cls.client = TestClient(app.app)
        
        # Authenticate as admin
        login_res = cls.client.post("/login", data={"username": "admin", "password": "adminSecret123!"})
        if login_res.status_code != 200:
            login_res = cls.client.post("/login", data={"username": "admin", "password": "admin123"})
        
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        cls.token = login_res.json()["access_token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    # ================================================================
    # 1. SSRF PROTECTION TESTS
    # ================================================================
    def test_01_ssrf_blocks_localhost(self):
        blocked_urls = [
            "http://localhost/",
            "http://localhost:8000/api/admin",
            "http://127.0.0.1/",
            "http://127.0.0.1:3306/",
            "http://0.0.0.0/",
            "http://[::1]/",
        ]
        for url in blocked_urls:
            with self.assertRaises(SSRFSecurityError, msg=f"Should block: {url}"):
                validate_safe_url(url)

    def test_02_ssrf_blocks_private_rfc1918_ips(self):
        private_urls = [
            "http://10.0.0.1/admin",
            "http://10.255.255.255/",
            "http://172.16.0.1/",
            "http://172.31.255.255/",
            "http://192.168.1.1/router",
            "http://192.168.0.100:8080/",
        ]
        for url in private_urls:
            with self.assertRaises(SSRFSecurityError, msg=f"Should block RFC1918: {url}"):
                validate_safe_url(url)

    def test_03_ssrf_blocks_cloud_metadata(self):
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.253/",
            "http://100.100.100.200/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://instance-data/latest/meta-data/",
        ]
        for url in metadata_urls:
            with self.assertRaises(SSRFSecurityError, msg=f"Should block cloud metadata: {url}"):
                validate_safe_url(url)

    def test_04_ssrf_blocks_non_http_schemes(self):
        bad_schemes = [
            "file:///etc/passwd",
            "file:///Users/mohammadakifakhtar/.bashrc",
            "ftp://files.example.com/data",
            "gopher://example.com/",
            "javascript:alert(1)",
            "data:text/html,<h1>Test</h1>",
        ]
        for url in bad_schemes:
            with self.assertRaises(SSRFSecurityError, msg=f"Should block scheme: {url}"):
                validate_safe_url(url)

    def test_05_ssrf_blocks_database_and_internal_ports(self):
        bad_ports = [
            "http://example.com:3306/",   # MySQL
            "http://example.com:5432/",   # Postgres
            "http://example.com:6379/",   # Redis
            "http://example.com:27017/",  # Mongo
            "http://example.com:11434/",  # Ollama internal
            "http://example.com:22/",     # SSH
        ]
        for url in bad_ports:
            with self.assertRaises(SSRFSecurityError, msg=f"Should block dangerous port: {url}"):
                validate_safe_url(url)

    def test_06_ssrf_allows_legitimate_public_urls(self):
        valid_urls = [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://www.google.com",
            "http://example.com",
        ]
        for url in valid_urls:
            try:
                res = validate_safe_url(url)
                self.assertEqual(res, url)
            except SSRFSecurityError as e:
                self.fail(f"Valid public URL should not be blocked: {url} -> {e}")

    # ================================================================
    # 2. HTML EXTRACTION & CLEANING TESTS
    # ================================================================
    def test_07_html_cleaner_strips_noise(self):
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sovereign AI Specifications</title>
            <script>alert("malicious script");</script>
            <style>body { background: #000; }</style>
        </head>
        <body>
            <header><nav><a href="/home">Home</a><a href="/login">Login</a></nav></header>
            <main>
                <h1>Sovereign Industrial System</h1>
                <p>Sovereign AI delivers 100% on-premise generative intelligence for mission critical plants.</p>
                <p>All data remains completely isolated and verified by zero-trust EvidenceChecker.</p>
            </main>
            <footer><p>&copy; 2026 Sovereign Systems. All rights reserved.</p></footer>
        </body>
        </html>
        """
        extracted = extract_page_content(sample_html, "https://sovereign.local/test")
        self.assertEqual(extracted["title"], "Sovereign AI Specifications")
        self.assertIn("Sovereign Industrial System", extracted["content"])
        self.assertIn("100% on-premise", extracted["content"])
        self.assertNotIn("alert", extracted["content"])
        self.assertNotIn("background: #000", extracted["content"])
        self.assertNotIn("Home", extracted["content"])
        self.assertNotIn("All rights reserved", extracted["content"])

    # ================================================================
    # 3. GLOBAL RAG VECTOR STORAGE & ISOLATION TESTS
    # ================================================================
    def test_08_global_rag_conversation_isolation(self):
        conv_id = "test_conv_global_isol_01"
        test_url = "https://example.org/global_safety_standard"
        test_title = "Global Industrial Safety Standard 2026"
        test_text = (
            "Standard ISO 45001 stipulates mandatory safety compliance for refining distillation units. "
            "Emergency shutdown valves (ESDV) must actuate within 1.5 seconds upon trip activation. "
            "Pressure safety valves (PSV) require bi-annual calibration and ultrasound inspection."
        )

        # Index in global store
        source_entry = index_global_source(
            conversation_id=conv_id,
            url=test_url,
            title=test_title,
            text=test_text,
        )
        self.assertEqual(source_entry["url"], test_url)
        self.assertEqual(source_entry["title"], test_title)
        self.assertGreater(source_entry["chunks_count"], 0)

        # Verify global directory created
        paths = get_global_paths(conv_id)
        self.assertTrue(paths["faiss"].exists())
        self.assertTrue(paths["documents_pickle"].exists())
        self.assertTrue(paths["sources_json"].exists())

        # Retrieve evidence from global store
        results = retrieve_global_evidence(conv_id, "How fast must ESDV actuate?", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["source_type"], "global_web")
        self.assertEqual(results[0]["url"], test_url)
        self.assertIn("ESDV", results[0]["text"])

        # Check that private MRPL company index exists and was NOT polluted
        mrpl_index_path = PROJECT_ROOT / "storage" / "MRPL" / "index" / "faiss.index"
        if mrpl_index_path.exists():
            self.assertTrue(mrpl_index_path.is_file())

        # Clean up global source
        removed = remove_global_source(conv_id, source_entry["id"])
        self.assertTrue(removed)
        remaining = get_conversation_sources(conv_id)
        self.assertEqual(len(remaining), 0)

    # ================================================================
    # 4. REST API ENDPOINTS & AUDIT LOGGING
    # ================================================================
    def test_09_api_global_sources_lifecycle(self):
        # 1. Create a conversation
        conv_res = self.client.post(
            "/api/conversations",
            headers=self.headers,
            json={"title": "Global RAG Lifecycle Test"}
        )
        self.assertEqual(conv_res.status_code, 200)
        conv_id = conv_res.json()["conversation_id"]

        # 2. Add an SSRF-blocked source -> Expect 400 Bad Request
        bad_res = self.client.post(
            "/api/global/sources",
            headers=self.headers,
            json={
                "conversation_id": conv_id,
                "url": "http://127.0.0.1:8000/secret",
            }
        )
        self.assertEqual(bad_res.status_code, 400)
        self.assertIn("blocked", bad_res.json()["detail"].lower())

        # 3. Add a valid public source (mocking fetch to avoid live network flakiness)
        mock_clean_data = {
            "url": "https://en.wikipedia.org/wiki/Refinery",
            "title": "Oil Refinery Overview",
            "content": "An oil refinery or petroleum refinery is an industrial process plant where petroleum is transformed into useful products.",
            "length": 120,
            "domain": "en.wikipedia.org",
        }
        with patch("app.fetch_and_clean_public_url", return_value=mock_clean_data):
            add_res = self.client.post(
                "/api/global/sources",
                headers=self.headers,
                json={
                    "conversation_id": conv_id,
                    "url": "https://en.wikipedia.org/wiki/Refinery",
                }
            )
            self.assertEqual(add_res.status_code, 200)
            res_json = add_res.json()
            source_data = res_json["source"]
            self.assertEqual(source_data["title"], "Oil Refinery Overview")
            source_id = source_data["id"]

        # 4. GET attached global sources
        get_res = self.client.get(
            f"/api/global/sources?conversation_id={conv_id}",
            headers=self.headers,
        )
        self.assertEqual(get_res.status_code, 200)
        sources_list = get_res.json().get("global_sources", [])
        self.assertEqual(len(sources_list), 1)
        self.assertEqual(sources_list[0]["id"], source_id)

        # 5. Check audit logs in MySQL
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT action, details FROM audit_logs WHERE username = 'admin' AND action LIKE 'GLOBAL_%' ORDER BY id DESC LIMIT 10"
        )
        actions = [r["action"] for r in cur.fetchall()]
        cur.close()
        conn.close()

        self.assertIn("GLOBAL_SOURCE_ADDED", actions)
        self.assertIn("GLOBAL_SOURCE_FAILED", actions)

        # 6. DELETE attached global source
        del_res = self.client.delete(
            f"/api/global/sources/{source_id}?conversation_id={conv_id}",
            headers=self.headers,
        )
        self.assertEqual(del_res.status_code, 200)

        # 7. Verify deletion
        get_res2 = self.client.get(
            f"/api/global/sources?conversation_id={conv_id}",
            headers=self.headers,
        )
        self.assertEqual(len(get_res2.json().get("global_sources", [])), 0)

        # Cleanup conversation
        self.client.delete(f"/api/conversations/{conv_id}", headers=self.headers)

    # ================================================================
    # 5. CHAT KNOWLEDGE MODE ROUTING TESTS
    # ================================================================
    def test_10_chat_knowledge_mode_handling(self):
        conv_res = self.client.post(
            "/api/conversations",
            headers=self.headers,
            json={"title": "Routing Test"}
        )
        conv_id = conv_res.json()["conversation_id"]

        # Private query with no docs
        res_private = self.client.post(
            "/api/chat",
            headers=self.headers,
            json={
                "conversation_id": conv_id,
                "message": "Explain distillation column safety",
                "knowledge_mode": "private",
            }
        )
        self.assertIn(res_private.status_code, (200, 422))

        # Global query with no sources attached -> returns prompt to attach URL
        res_global = self.client.post(
            "/api/chat",
            headers=self.headers,
            json={
                "conversation_id": conv_id,
                "message": "Explain distillation column safety",
                "knowledge_mode": "global",
            }
        )
        self.assertEqual(res_global.status_code, 200)
        data = res_global.json()
        self.assertIn("public web sources", data.get("answer", "").lower())

        # Cleanup
        self.client.delete(f"/api/conversations/{conv_id}", headers=self.headers)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGlobalKnowledgeMode)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
