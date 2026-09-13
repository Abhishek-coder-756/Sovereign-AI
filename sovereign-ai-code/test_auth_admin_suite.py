"""
Comprehensive Verification Suite for Sovereign AI (SIH26117)
Authentication, Registration Approval, Role-based Password Prefixes,
Admin Panel & User Management, MySQL Audit Logging, and System Health.
"""

import sys
import uuid
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path("/Users/mohammadakifakhtar/PROGRAM/Jupyter/sovereign-ai-final")
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app import app
from db import get_connection
from backend.app.security.users import get_user, count_active_admins

client = TestClient(app)

TOTAL_TESTS = 0
PASSED_TESTS = 0
FAILED_TESTS = []


def record_test(name: str, condition: bool, details: str = ""):
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1
    if condition:
        PASSED_TESTS += 1
        print(f"  \033[92m[PASS]\033[0m {name}")
    else:
        FAILED_TESTS.append((name, details))
        print(f"  \033[91m[FAIL]\033[0m {name} - {details}")


def run_all_tests():
    print("\n" + "=" * 70)
    print("SOVEREIGN AI (SIH26117) — COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 70 + "\n")

    # ================================================================
    # 1. DATABASE TESTS
    # ================================================================
    print("1. DATABASE INTEGRITY TESTS:")
    conn = get_connection()
    record_test("MySQL connection succeeds", conn is not None and conn.is_connected())

    cur = conn.cursor(dictionary=True)
    cur.execute("SHOW TABLES")
    tables = {list(r.values())[0] for r in cur.fetchall()}
    required_tables = {"companies", "users", "conversations", "messages", "uploaded_files", "audit_logs"}
    record_test("All 6 existing tables preserved", required_tables.issubset(tables), f"Found: {tables}")

    # Check existing users preserved
    cur.execute("SELECT username, role, status FROM users WHERE username IN ('admin', 'operator', 'other_user')")
    existing_users = {r["username"]: r for r in cur.fetchall()}
    record_test("Existing admin user preserved", "admin" in existing_users and existing_users["admin"]["role"] == "admin")
    record_test("Existing operator user preserved", "operator" in existing_users and existing_users["operator"]["role"] == "operator")
    record_test("Existing other_user preserved", "other_user" in existing_users)
    record_test("Existing admin is APPROVED", existing_users.get("admin", {}).get("status") == "APPROVED")

    # Check columns in users
    cur.execute("DESCRIBE users")
    user_cols = {r["Field"] for r in cur.fetchall()}
    req_cols = {"name", "mobile", "status", "created_at", "updated_at", "approved_at", "approved_by", "deleted_at", "deleted_by", "last_login_at"}
    record_test("All required fields exist in users table", req_cols.issubset(user_cols), f"Missing: {req_cols - user_cols}")

    # Check columns in audit_logs
    cur.execute("DESCRIBE audit_logs")
    audit_cols = {r["Field"] for r in cur.fetchall()}
    req_audit_cols = {"user_id", "target_user_id", "target_username", "target_role"}
    record_test("All required target fields exist in audit_logs", req_audit_cols.issubset(audit_cols))

    cur.close()
    conn.close()

    # ================================================================
    # 2. REGISTRATION & ROLE PASSWORD PREFIX VALIDATION
    # ================================================================
    print("\n2. REGISTRATION & PASSWORD PREFIX TESTS:")

    suffix = uuid.uuid4().hex[:6]
    test_emp_user = f"emp_test_{suffix}"
    test_op_user = f"op_test_{suffix}"
    test_admin_user = f"adm_test_{suffix}"

    # Invalid Admin prefix
    r = client.post("/api/register", json={
        "name": "Test Admin",
        "username": f"bad_adm_{suffix}",
        "mobile": "+919876543210",
        "role": "admin",
        "password": "wrongPrefixPassword123",
        "confirm_password": "wrongPrefixPassword123",
        "company": "MRPL"
    })
    record_test("Admin registration fails without 'admin' prefix", r.status_code == 422 and "admin" in r.text.lower())

    # Invalid Operator prefix
    r = client.post("/api/register", json={
        "name": "Test Op",
        "username": f"bad_op_{suffix}",
        "mobile": "+919876543210",
        "role": "operator",
        "password": "wrongPrefixPassword123",
        "confirm_password": "wrongPrefixPassword123",
        "company": "MRPL"
    })
    record_test("Operator registration fails without 'operator' prefix", r.status_code == 422 and "operator" in r.text.lower())

    # Invalid Employee prefix
    r = client.post("/api/register", json={
        "name": "Test Emp",
        "username": f"bad_emp_{suffix}",
        "mobile": "+919876543210",
        "role": "employee",
        "password": "wrongPrefixPassword123",
        "confirm_password": "wrongPrefixPassword123",
        "company": "MRPL"
    })
    record_test("Employee registration fails without 'emp' prefix", r.status_code == 422 and "emp" in r.text.lower())

    # Password mismatch
    r = client.post("/api/register", json={
        "name": "Test Emp",
        "username": f"mismatch_{suffix}",
        "mobile": "+919876543210",
        "role": "employee",
        "password": "empPassword123!",
        "confirm_password": "empPasswordDifferent!",
        "company": "MRPL"
    })
    record_test("Registration fails on password confirmation mismatch", r.status_code == 422 and "match" in r.text.lower())

    # Password too short
    r = client.post("/api/register", json={
        "name": "Test Emp",
        "username": f"short_{suffix}",
        "mobile": "+919876543210",
        "role": "employee",
        "password": "emp1",
        "confirm_password": "emp1",
        "company": "MRPL"
    })
    record_test("Registration fails when password is too short", r.status_code == 422)

    # Invalid role
    r = client.post("/api/register", json={
        "name": "Test Hacker",
        "username": f"hack_{suffix}",
        "mobile": "+919876543210",
        "role": "super_root",
        "password": "superPassword123!",
        "confirm_password": "superPassword123!",
        "company": "MRPL"
    })
    record_test("Registration fails on arbitrary/invalid role", r.status_code == 422)

    # Valid Employee Registration
    emp_pw = "empSecretPass2026!"
    r = client.post("/api/register", json={
        "name": "Akif Employee",
        "username": test_emp_user,
        "mobile": "+91 9876543210",
        "role": "employee",
        "password": emp_pw,
        "confirm_password": emp_pw,
        "company": "MRPL"
    })
    record_test("Valid employee registration succeeds", r.status_code == 200 and r.json().get("status") == "PENDING")

    # Valid Operator Registration
    op_pw = "operatorSecret2026!"
    r = client.post("/api/register", json={
        "name": "Akif Operator",
        "username": test_op_user,
        "mobile": "+91 9876543211",
        "role": "operator",
        "password": op_pw,
        "confirm_password": op_pw,
        "company": "MRPL"
    })
    record_test("Valid operator registration succeeds", r.status_code == 200 and r.json().get("status") == "PENDING")

    # Duplicate username check
    r = client.post("/api/register", json={
        "name": "Duplicate User",
        "username": test_emp_user,
        "mobile": "+91 9876543212",
        "role": "employee",
        "password": emp_pw,
        "confirm_password": emp_pw,
        "company": "MRPL"
    })
    record_test("Duplicate username registration rejected with 409", r.status_code == 409)

    # Verify DB: password hash is stored, plaintext never stored
    user_row = get_user(test_emp_user)
    record_test("New user initial status in MySQL is PENDING", user_row is not None and user_row["status"] == "PENDING")
    record_test("Password hash is stored (starts with $2b$)", user_row is not None and user_row["password"].startswith("$2b$"))
    record_test("Plaintext password is NEVER stored in database", user_row is not None and user_row["password"] != emp_pw)

    # ================================================================
    # 3. LOGIN & STATUS WORKFLOW TESTS
    # ================================================================
    print("\n3. LOGIN & APPROVAL WORKFLOW TESTS:")

    # Attempt login while PENDING
    r = client.post("/login", data={"username": test_emp_user, "password": emp_pw})
    record_test("Pending account login blocked with 403", r.status_code == 403)
    record_test("Pending error message matches requirement", "waiting for administrator approval" in r.text)

    # Login as existing admin
    admin_login_res = client.post("/login", data={"username": "admin", "password": "admin123"})
    record_test("Approved admin login succeeds", admin_login_res.status_code == 200 and "access_token" in admin_login_res.json())
    admin_token = admin_login_res.json().get("access_token", "")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Wrong password fails
    r = client.post("/login", data={"username": "admin", "password": "adminWrongPassword!"})
    record_test("Wrong password login fails with 401", r.status_code == 401 and "Invalid username or password" in r.text)

    # Admin approves employee user
    emp_db_id = user_row["id"]
    r = client.post(f"/api/admin/users/{emp_db_id}/approve", headers=admin_headers)
    record_test("Admin can approve pending employee", r.status_code == 200 and r.json().get("success") is True)

    # Approved employee can now login
    emp_login_res = client.post("/login", data={"username": test_emp_user, "password": emp_pw})
    record_test("Approved employee login succeeds", emp_login_res.status_code == 200 and "access_token" in emp_login_res.json())
    emp_token = emp_login_res.json().get("access_token", "")
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Admin rejects operator user
    op_user_row = get_user(test_op_user)
    op_db_id = op_user_row["id"]
    r = client.post(f"/api/admin/users/{op_db_id}/reject", headers=admin_headers)
    record_test("Admin can reject pending operator", r.status_code == 200 and r.json().get("success") is True)

    # Rejected operator tries to login
    r = client.post("/login", data={"username": test_op_user, "password": op_pw})
    record_test("Rejected account login blocked with 403", r.status_code == 403)
    record_test("Rejected error message matches requirement", "registration was rejected" in r.text)

    # Admin disables employee
    r = client.post(f"/api/admin/users/{emp_db_id}/disable", headers=admin_headers)
    record_test("Admin can disable user", r.status_code == 200)

    # Disabled employee tries to login
    r = client.post("/login", data={"username": test_emp_user, "password": emp_pw})
    record_test("Disabled account login blocked with 403", r.status_code == 403)
    record_test("Disabled error message matches requirement", "account has been disabled" in r.text)

    # Stale token test: calling API with token issued before being disabled
    r = client.get("/api/me", headers=emp_headers)
    record_test("Disabled user rejected on protected endpoint with stale token", r.status_code in (401, 403))

    # Admin re-enables employee
    r = client.post(f"/api/admin/users/{emp_db_id}/enable", headers=admin_headers)
    record_test("Admin can re-enable user", r.status_code == 200)

    # Employee logs in again
    r = client.post("/login", data={"username": test_emp_user, "password": emp_pw})
    record_test("Re-enabled employee login succeeds", r.status_code == 200)
    emp_token = r.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # ================================================================
    # 4. RBAC & ADMIN ENDPOINT SECURITY TESTS
    # ================================================================
    print("\n4. RBAC & ADMIN SECURITY TESTS:")

    # Employee tries to access admin endpoints
    r = client.get("/api/admin/stats", headers=emp_headers)
    record_test("Employee cannot access admin stats (403)", r.status_code == 403)

    r = client.get("/api/admin/users", headers=emp_headers)
    record_test("Employee cannot access admin user list (403)", r.status_code == 403)

    r = client.post(f"/api/admin/users/{op_db_id}/approve", headers=emp_headers)
    record_test("Employee cannot approve users (403)", r.status_code == 403)

    r = client.delete(f"/api/admin/users/{op_db_id}", headers=emp_headers)
    record_test("Employee cannot delete users (403)", r.status_code == 403)

    # Existing operator tries to access admin endpoints
    op_login_res = client.post("/login", data={"username": "operator", "password": "operator123"})
    record_test("Approved operator login succeeds", op_login_res.status_code == 200)
    op_token = op_login_res.json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    r = client.get("/api/admin/stats", headers=op_headers)
    record_test("Operator cannot access admin stats (403)", r.status_code == 403)

    r = client.get("/api/admin/pending", headers=op_headers)
    record_test("Operator cannot access admin pending requests (403)", r.status_code == 403)

    # Admin accesses admin endpoints
    r = client.get("/api/admin/stats", headers=admin_headers)
    record_test("Admin can access stats endpoint (200)", r.status_code == 200)
    stats_data = r.json()
    record_test("Stats returns all required keys", {"total_users", "pending", "approved", "active", "disabled", "employees", "operators", "admins"}.issubset(stats_data.keys()))

    r = client.get("/api/admin/pending", headers=admin_headers)
    record_test("Admin can access pending list (200)", r.status_code == 200 and isinstance(r.json(), list))

    r = client.get("/api/admin/users", headers=admin_headers)
    record_test("Admin can access users list (200)", r.status_code == 200 and isinstance(r.json(), list))

    # Password hashes are NEVER returned in users list
    user_list = r.json()
    has_pw = any("password" in u for u in user_list)
    record_test("Password hashes never exposed in admin users list", not has_pw)

    # Last active admin protection
    admin_row = get_user("admin")
    r = client.delete(f"/api/admin/users/{admin_row['id']}", headers=admin_headers)
    record_test("Cannot delete the last active administrator (400)", r.status_code == 400 and "last active administrator" in r.text)

    r = client.post(f"/api/admin/users/{admin_row['id']}/disable", headers=admin_headers)
    record_test("Cannot disable the last active administrator (400)", r.status_code == 400 and "last active administrator" in r.text)

    # ================================================================
    # 5. USER MANAGEMENT & SOFT DELETE
    # ================================================================
    print("\n5. USER MANAGEMENT & SOFT DELETE TESTS:")

    r = client.delete(f"/api/admin/users/{emp_db_id}", headers=admin_headers)
    record_test("Admin can remove/delete employee", r.status_code == 200 and r.json().get("success") is True)

    del_user_row = get_user(test_emp_user)
    record_test("User status changed to DELETED", del_user_row["status"] == "DELETED")
    record_test("deleted_at timestamp is set", del_user_row["deleted_at"] is not None)
    record_test("deleted_by is set to admin", del_user_row["deleted_by"] == "admin")

    r = client.post("/login", data={"username": test_emp_user, "password": emp_pw})
    record_test("Deleted user cannot log in (403)", r.status_code == 403 and "disabled" in r.text)

    # ================================================================
    # 6. AUDIT LOGGING TESTS
    # ================================================================
    print("\n6. AUDIT LOGGING VERIFICATION:")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT action, status, username, target_username, details FROM audit_logs ORDER BY id DESC LIMIT 50")
    audit_rows = cur.fetchall()
    cur.close()
    conn.close()

    actions = {r["action"] for r in audit_rows}
    record_test("USER_REGISTER logged in MySQL audit_logs", "USER_REGISTER" in actions)
    record_test("LOGIN logged in MySQL audit_logs", "LOGIN" in actions)
    record_test("USER_APPROVED logged in MySQL audit_logs", "USER_APPROVED" in actions)
    record_test("USER_REJECTED logged in MySQL audit_logs", "USER_REJECTED" in actions)
    record_test("USER_DISABLED logged in MySQL audit_logs", "USER_DISABLED" in actions)
    record_test("USER_ENABLED logged in MySQL audit_logs", "USER_ENABLED" in actions)
    record_test("USER_DELETED logged in MySQL audit_logs", "USER_DELETED" in actions)

    # Admin audit endpoint
    r = client.get("/api/admin/audit", headers=admin_headers)
    record_test("Admin audit endpoint returns audit events (200)", r.status_code == 200 and len(r.json()) > 0)

    # Check that passwords / hashes are never logged in details
    has_leak = any(emp_pw in str(r.get("details", "")) or "$2b$" in str(r.get("details", "")) for r in audit_rows)
    record_test("Passwords and hashes are never exposed in audit logs", not has_leak)

    # ================================================================
    # 7. EXISTING SYSTEM FUNCTIONALITY TESTS
    # ================================================================
    print("\n7. EXISTING SYSTEM PRESERVATION TESTS:")

    # Health endpoint
    r = client.get("/api/health")
    record_test("Health endpoint /api/health succeeds", r.status_code == 200 and r.json().get("status") == "ok")

    # Documents endpoint
    r = client.get("/api/documents", headers=admin_headers)
    record_test("Documents endpoint /api/documents succeeds", r.status_code == 200 and isinstance(r.json(), list))

    # Conversations endpoint
    r = client.get("/api/conversations", headers=admin_headers)
    record_test("Conversations endpoint /api/conversations succeeds", r.status_code == 200 and isinstance(r.json(), list))

    # Create conversation
    r = client.post("/api/conversations", headers=admin_headers, json={"title": "Verification Test Chat"})
    record_test("Create conversation succeeds", r.status_code == 200 and "conversation_id" in r.json())
    conv_id = r.json().get("conversation_id")

    # Delete conversation
    if conv_id:
        r = client.delete(f"/api/conversations/{conv_id}", headers=admin_headers)
        record_test("Delete conversation succeeds", r.status_code == 200)

    # Company Isolation
    other_login = client.post("/login", data={"username": "other_user", "password": "other123"})
    record_test("Other company admin can login", other_login.status_code == 200)
    other_token = other_login.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    r = client.get("/api/admin/users", headers=other_headers)
    other_users_list = r.json()
    record_test("Company isolation: other company admin cannot see MRPL users", all(u.get("company") == "OTHER_COMPANY" for u in other_users_list))

    print("\n" + "=" * 70)
    print(f"RESULTS: {PASSED_TESTS}/{TOTAL_TESTS} TESTS PASSED ({round(PASSED_TESTS/TOTAL_TESTS*100, 1)}%)")
    if FAILED_TESTS:
        print("\nFAILURES:")
        for f, d in FAILED_TESTS:
            print(f"  - {f}: {d}")
    print("=" * 70 + "\n")

    return len(FAILED_TESTS) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
