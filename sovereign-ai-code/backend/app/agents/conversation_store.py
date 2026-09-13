"""
Conversation Store for Persistent ChatGPT-style Chat Sessions.
Sovereign On-Premise Agentic AI Workbench — SIH26117.

Stores conversations locally on disk:
    data/conversations/<conversation_id>.json

Strictly isolated per company and username.
Survives server restarts.
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONVERSATIONS_DIR = PROJECT_ROOT / "data" / "conversations"
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


def _get_conversation_path(conversation_id: str) -> Path:
    # Sanitize conversation_id to avoid path traversal
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(conversation_id))
    return CONVERSATIONS_DIR / f"{safe_id}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_title(first_query: str) -> str:
    """
    Generate a clean conversation title from the first user query.
    """
    if not first_query:
        return "New Chat"
    
    clean = first_query.strip()
    # Remove common conversational prefixes
    prefixes = [
        "what is the", "what are the", "what is this", "what does",
        "can you", "please", "analyze", "explain", "tell me about",
        "how to", "check", "according to the"
    ]
    lowered = clean.lower()
    for p in prefixes:
        if lowered.startswith(p):
            remainder = clean[len(p):].strip(" ?:.,-")
            if len(remainder) > 3:
                clean = remainder
            break

    # Truncate nicely
    words = clean.split()
    if len(words) > 6:
        title = " ".join(words[:6]) + "..."
    else:
        title = clean
    
    # Capitalize first letter
    if title:
        title = title[0].upper() + title[1:]
    return title[:45] if title else "New Chat"


class ConversationStore:
    """
    Local JSON-based conversation storage.
    Enforces user and company isolation.
    """

    @staticmethod
    def create_conversation(
        company: str,
        username: str,
        title: str = "New Chat"
    ) -> Dict[str, Any]:
        conv_id = f"c_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        data = {
            "conversation_id": conv_id,
            "title": title,
            "company": company,
            "username": username,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "uploaded_files": [],
            "uploaded_images": [],
            "global_sources": [],
        }
        path = _get_conversation_path(conv_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data

    @staticmethod
    def get_conversation(
        company: str,
        username: str,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        path = _get_conversation_path(conversation_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Company and user security check
            if data.get("company") != company or data.get("username") != username:
                return None
            return data
        except Exception:
            return None

    @staticmethod
    def list_conversations(
        company: str,
        username: str
    ) -> List[Dict[str, Any]]:
        CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        results = []
        for path in CONVERSATIONS_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("company") == company and data.get("username") == username:
                    # Return metadata summary for sidebar
                    results.append({
                        "conversation_id": data["conversation_id"],
                        "title": data.get("title", "Untitled Chat"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "message_count": len(data.get("messages", [])),
                        "file_count": len(data.get("uploaded_files", [])),
                        "image_count": len(data.get("uploaded_images", [])),
                        "uploaded_files": data.get("uploaded_files", []),
                        "uploaded_images": data.get("uploaded_images", []),
                        "global_sources": data.get("global_sources", []),
                    })
            except Exception:
                continue

        # Sort newest updated first
        results.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return results

    @staticmethod
    def update_conversation(
        company: str,
        username: str,
        conversation_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        existing = ConversationStore.get_conversation(company, username, conversation_id)
        if not existing:
            return None
        
        data["updated_at"] = _now_iso()
        data["company"] = company
        data["username"] = username
        data["conversation_id"] = conversation_id
        path = _get_conversation_path(conversation_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data

    @staticmethod
    def add_message(
        company: str,
        username: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return None
        
        msg = {
            "role": role,
            "content": content,
            "timestamp": _now_iso()
        }
        if metadata:
            msg["metadata"] = metadata

        conv["messages"].append(msg)
        conv["updated_at"] = _now_iso()

        # Update title if it's the first user message and title is default
        if role == "user" and (conv.get("title") in ("New Chat", "Untitled Chat", "") or len(conv["messages"]) == 1):
            conv["title"] = generate_title(content)

        return ConversationStore.update_conversation(company, username, conversation_id, conv)

    @staticmethod
    def attach_file(
        company: str,
        username: str,
        conversation_id: str,
        filename: str,
        file_path: Optional[str] = None,
        category: str = "document"
    ) -> Optional[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return None
        
        uploaded_files = conv.setdefault("uploaded_files", [])
        # Avoid duplicate entries
        if filename not in uploaded_files:
            uploaded_files.append(filename)
        
        conv["updated_at"] = _now_iso()
        return ConversationStore.update_conversation(company, username, conversation_id, conv)

    @staticmethod
    def attach_image(
        company: str,
        username: str,
        conversation_id: str,
        image_path: str,
        filename: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return None
        
        uploaded_images = conv.setdefault("uploaded_images", [])
        # Store image path / filename
        entry = image_path
        if entry not in uploaded_images:
            uploaded_images.append(entry)
        
        conv["updated_at"] = _now_iso()
        return ConversationStore.update_conversation(company, username, conversation_id, conv)

    @staticmethod
    def remove_attachment(
        company: str,
        username: str,
        conversation_id: str,
        filename: str
    ) -> Optional[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return None
        
        conv["uploaded_files"] = [
            f for f in conv.get("uploaded_files", [])
            if f != filename
        ]
        conv["uploaded_images"] = [
            img for img in conv.get("uploaded_images", [])
            if Path(img).name != filename and img != filename
        ]
        conv["updated_at"] = _now_iso()
        return ConversationStore.update_conversation(company, username, conversation_id, conv)

    @staticmethod
    def attach_global_source(
        company: str,
        username: str,
        conversation_id: str,
        source: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return None

        sources = conv.setdefault("global_sources", [])
        # Avoid duplicate URL
        existing_idx = next((i for i, s in enumerate(sources) if s.get("url") == source.get("url")), None)
        if existing_idx is not None:
            sources[existing_idx] = source
        else:
            sources.append(source)

        conv["updated_at"] = _now_iso()
        return ConversationStore.update_conversation(company, username, conversation_id, conv)

    @staticmethod
    def remove_global_source(
        company: str,
        username: str,
        conversation_id: str,
        source_id_or_url: Any
    ) -> Optional[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return None

        conv["global_sources"] = [
            s for s in conv.get("global_sources", [])
            if str(s.get("id")) != str(source_id_or_url) and s.get("url") != str(source_id_or_url)
        ]
        conv["updated_at"] = _now_iso()
        return ConversationStore.update_conversation(company, username, conversation_id, conv)

    @staticmethod
    def get_global_sources(
        company: str,
        username: str,
        conversation_id: str
    ) -> List[Dict[str, Any]]:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return []
        return conv.get("global_sources", [])

    @staticmethod
    def delete_conversation(
        company: str,
        username: str,
        conversation_id: str
    ) -> bool:
        conv = ConversationStore.get_conversation(company, username, conversation_id)
        if not conv:
            return False
        
        path = _get_conversation_path(conversation_id)
        try:
            if path.exists():
                path.unlink()
            return True
        except Exception:
            return False


# Module-level aliases
attach_global_source = ConversationStore.attach_global_source
remove_global_source = ConversationStore.remove_global_source
get_global_sources = ConversationStore.get_global_sources

