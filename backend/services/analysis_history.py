"""
Analysis History Service.

Stores and retrieves AI CMO analysis history with timestamps.
This allows users to review past analyses and understand when they were run.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")

# Store history in connectors/data directory alongside other data
DATA_DIR = Path(__file__).parent.parent.parent / "connectors" / "data"
HISTORY_FILE = DATA_DIR / "ai_analysis_history.json"


def _load_history() -> list[dict]:
    """Load history from file."""
    if not HISTORY_FILE.exists():
        return []

    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_history(history: list[dict]) -> None:
    """Save history to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)


def save_analysis(
    synthesis: str,
    recommendations_extracted: list[dict],
    question: Optional[str] = None,
    days: int = 30,
    usage: Optional[dict] = None,
) -> dict:
    """
    Save an analysis to history.

    Args:
        synthesis: The full synthesis text from the AI
        recommendations_extracted: List of extracted recommendations
        question: Optional user question that prompted the analysis
        days: Number of days analyzed
        usage: Token usage info

    Returns:
        The saved history entry
    """
    history = _load_history()

    # Create a unique ID based on timestamp
    now = datetime.now(EST)
    entry_id = now.strftime("%Y%m%d_%H%M%S")

    # Extract a brief summary from the synthesis (first 200 chars of executive summary)
    summary = ""
    if "### Executive Summary" in synthesis:
        start = synthesis.find("### Executive Summary")
        end = synthesis.find("###", start + 20)
        if end == -1:
            end = start + 500
        summary = synthesis[start + 22:end].strip()[:200]
    elif "## Executive Summary" in synthesis:
        start = synthesis.find("## Executive Summary")
        end = synthesis.find("##", start + 20)
        if end == -1:
            end = start + 500
        summary = synthesis[start + 21:end].strip()[:200]
    else:
        # Just take the first 200 chars
        summary = synthesis[:200].strip()

    # Count recommendations by type
    rec_counts = {}
    for rec in recommendations_extracted:
        rec_type = rec.get("type", "other")
        rec_counts[rec_type] = rec_counts.get(rec_type, 0) + 1

    entry = {
        "id": entry_id,
        "timestamp": now.isoformat(),
        "timestamp_display": now.strftime("%b %d, %Y at %I:%M %p EST"),
        "question": question,
        "days_analyzed": days,
        "summary": summary,
        "synthesis": synthesis,
        "recommendations_count": len(recommendations_extracted),
        "recommendations_by_type": rec_counts,
        "recommendations": recommendations_extracted,
        "usage": usage or {},
    }

    # Add to the beginning of history (newest first)
    history.insert(0, entry)

    # Keep last 100 entries to prevent file from growing too large
    history = history[:100]

    _save_history(history)

    return entry


def get_history(limit: int = 20, offset: int = 0) -> dict:
    """
    Get analysis history.

    Args:
        limit: Maximum number of entries to return
        offset: Offset for pagination

    Returns:
        Dictionary with entries and total count
    """
    history = _load_history()

    total = len(history)
    entries = history[offset:offset + limit]

    # Return lightweight entries without full synthesis for listing
    lightweight_entries = []
    for entry in entries:
        lightweight_entries.append({
            "id": entry["id"],
            "timestamp": entry["timestamp"],
            "timestamp_display": entry["timestamp_display"],
            "question": entry.get("question"),
            "days_analyzed": entry.get("days_analyzed", 30),
            "summary": entry.get("summary", ""),
            "recommendations_count": entry.get("recommendations_count", 0),
            "recommendations_by_type": entry.get("recommendations_by_type", {}),
        })

    return {
        "entries": lightweight_entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


def get_analysis_by_id(entry_id: str) -> Optional[dict]:
    """
    Get a specific analysis by ID.

    Args:
        entry_id: The analysis ID

    Returns:
        Full analysis entry or None if not found
    """
    history = _load_history()

    for entry in history:
        if entry["id"] == entry_id:
            return entry

    return None


def delete_analysis(entry_id: str) -> bool:
    """
    Delete an analysis from history.

    Args:
        entry_id: The analysis ID to delete

    Returns:
        True if deleted, False if not found
    """
    history = _load_history()

    for i, entry in enumerate(history):
        if entry["id"] == entry_id:
            history.pop(i)
            _save_history(history)
            return True

    return False
