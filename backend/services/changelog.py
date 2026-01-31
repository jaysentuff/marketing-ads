"""
Changelog service for tracking marketing decisions and actions.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

CHANGELOG_FILE = Path(__file__).parent.parent.parent / "connectors" / "data" / "changelog.json"


def load_changelog() -> list[dict]:
    """Load the changelog from file."""
    try:
        with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_changelog(entries: list[dict]):
    """Save the changelog to file."""
    CHANGELOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def add_entry(
    action_type: str,
    description: str,
    channel: Optional[str] = None,
    campaign: Optional[str] = None,
    amount: Optional[float] = None,
    percent_change: Optional[float] = None,
    original_budget: Optional[float] = None,
    notes: Optional[str] = None,
    metrics_snapshot: Optional[dict] = None,
    timestamp: Optional[str] = None,
) -> dict:
    """Add a new entry to the changelog."""
    entries = load_changelog()

    # Get max existing ID to avoid duplicates
    max_id = max((e.get("id", 0) for e in entries), default=0)

    entry = {
        "id": max_id + 1,
        "timestamp": timestamp or datetime.now().isoformat(),
        "action_type": action_type,
        "description": description,
        "channel": channel,
        "campaign": campaign,
        "amount": amount,
        "percent_change": percent_change,
        "original_budget": original_budget,
        "notes": notes,
        "metrics_snapshot": metrics_snapshot or {},
    }

    entries.append(entry)
    save_changelog(entries)

    return entry


def get_recent_entries(days: int = 30, limit: int = 50) -> list[dict]:
    """Get recent changelog entries."""
    entries = load_changelog()
    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    if days:
        cutoff = datetime.now() - timedelta(days=days)
        entries = [
            e for e in entries
            if datetime.fromisoformat(e.get("timestamp", "2000-01-01")) >= cutoff
        ]

    return entries[:limit]


def get_entries_summary() -> str:
    """Get a text summary of recent changes for AI context."""
    entries = get_recent_entries(days=14, limit=10)

    if not entries:
        return "No recent changes logged."

    lines = ["Recent marketing changes (last 14 days):"]

    for e in entries:
        date = e.get("timestamp", "")[:10]
        action = e.get("description", "Unknown action")
        channel = e.get("channel", "")
        notes = e.get("notes", "")

        line = f"- {date}: {action}"
        if channel:
            line += f" ({channel})"
        if notes:
            line += f" - Note: {notes}"

        lines.append(line)

    return "\n".join(lines)


def delete_entry(entry_id: int) -> bool:
    """Delete an entry by ID."""
    entries = load_changelog()
    original_len = len(entries)

    entries = [e for e in entries if e.get("id") != entry_id]

    if len(entries) < original_len:
        save_changelog(entries)
        return True

    return False


def update_entry(
    entry_id: int,
    description: Optional[str] = None,
    amount: Optional[float] = None,
    percent_change: Optional[float] = None,
    original_budget: Optional[float] = None,
    notes: Optional[str] = None,
    channel: Optional[str] = None,
    campaign: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Optional[dict]:
    """Update an existing changelog entry."""
    entries = load_changelog()

    for entry in entries:
        if entry.get("id") == entry_id:
            if description is not None:
                entry["description"] = description
            if amount is not None:
                entry["amount"] = amount
            if percent_change is not None:
                entry["percent_change"] = percent_change
            if original_budget is not None:
                entry["original_budget"] = original_budget
            if notes is not None:
                entry["notes"] = notes
            if channel is not None:
                entry["channel"] = channel
            if campaign is not None:
                entry["campaign"] = campaign
            if timestamp is not None:
                entry["timestamp"] = timestamp

            save_changelog(entries)
            return entry

    return None


ACTION_TYPES = [
    ("spend_increase", "Increased Spend"),
    ("spend_decrease", "Decreased Spend"),
    ("campaign_paused", "Paused Campaign"),
    ("campaign_launched", "Launched Campaign"),
    ("creative_change", "Changed Creative"),
    ("targeting_change", "Changed Targeting"),
    ("budget_shift", "Shifted Budget"),
    ("other", "Other"),
]
