"""
Chat history service for persisting AI chat conversations.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from uuid import uuid4

DATA_DIR = Path(__file__).parent.parent.parent / "connectors" / "data"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"


def _ensure_file():
    """Ensure the chat history file exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CHAT_HISTORY_FILE.exists():
        CHAT_HISTORY_FILE.write_text(json.dumps({"sessions": []}, indent=2))


def _load_data() -> dict:
    """Load chat history data."""
    _ensure_file()
    try:
        return json.loads(CHAT_HISTORY_FILE.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return {"sessions": []}


def _save_data(data: dict):
    """Save chat history data."""
    _ensure_file()
    CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2))


def get_all_sessions() -> list:
    """Get all chat sessions (without full messages for performance)."""
    data = _load_data()
    sessions = data.get("sessions", [])
    # Return summary without full message content
    return [
        {
            "id": s["id"],
            "title": s.get("title", "Untitled Chat"),
            "created_at": s.get("created_at"),
            "updated_at": s.get("updated_at"),
            "message_count": len(s.get("messages", [])),
            "preview": s.get("messages", [{}])[0].get("content", "")[:100] if s.get("messages") else ""
        }
        for s in sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    ]


def get_session(session_id: str) -> Optional[dict]:
    """Get a specific chat session by ID."""
    data = _load_data()
    for session in data.get("sessions", []):
        if session["id"] == session_id:
            return session
    return None


def create_session(title: Optional[str] = None) -> dict:
    """Create a new chat session."""
    data = _load_data()
    now = datetime.now().isoformat()

    session = {
        "id": str(uuid4()),
        "title": title or f"Chat {len(data['sessions']) + 1}",
        "created_at": now,
        "updated_at": now,
        "messages": []
    }

    data["sessions"].append(session)
    _save_data(data)
    return session


def update_session(session_id: str, messages: list, title: Optional[str] = None) -> Optional[dict]:
    """Update a chat session with new messages."""
    data = _load_data()

    for i, session in enumerate(data["sessions"]):
        if session["id"] == session_id:
            session["messages"] = messages
            session["updated_at"] = datetime.now().isoformat()

            # Auto-generate title from first user message if not set
            if title:
                session["title"] = title
            elif messages and session.get("title", "").startswith("Chat "):
                first_user_msg = next((m for m in messages if m.get("role") == "user"), None)
                if first_user_msg:
                    content = first_user_msg["content"][:50]
                    session["title"] = content + ("..." if len(first_user_msg["content"]) > 50 else "")

            data["sessions"][i] = session
            _save_data(data)
            return session

    return None


def delete_session(session_id: str) -> bool:
    """Delete a chat session."""
    data = _load_data()
    original_length = len(data["sessions"])
    data["sessions"] = [s for s in data["sessions"] if s["id"] != session_id]

    if len(data["sessions"]) < original_length:
        _save_data(data)
        return True
    return False
