"""
Changelog system for tracking marketing decisions and actions.

Stores a history of actions taken so the AI can reference past decisions
when giving advice.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

CHANGELOG_FILE = Path(__file__).parent.parent / "connectors" / "data" / "changelog.json"


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
    notes: Optional[str] = None,
    metrics_snapshot: Optional[dict] = None,
) -> dict:
    """
    Add a new entry to the changelog.

    Args:
        action_type: Type of action (spend_increase, spend_decrease, campaign_paused,
                     campaign_launched, creative_change, targeting_change, other)
        description: Brief description of what was done
        channel: Google Ads, Meta Ads, etc.
        campaign: Campaign name if applicable
        amount: Dollar amount if applicable
        percent_change: Percentage change if applicable
        notes: Additional notes
        metrics_snapshot: Current metrics at time of change (CAM, ROAS, etc.)

    Returns:
        The created entry
    """
    entries = load_changelog()

    entry = {
        "id": len(entries) + 1,
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "description": description,
        "channel": channel,
        "campaign": campaign,
        "amount": amount,
        "percent_change": percent_change,
        "notes": notes,
        "metrics_snapshot": metrics_snapshot or {},
    }

    entries.append(entry)
    save_changelog(entries)

    return entry


def get_recent_entries(days: int = 30, limit: int = 50) -> list[dict]:
    """Get recent changelog entries."""
    entries = load_changelog()

    # Sort by timestamp descending
    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Filter by date if needed
    if days:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)

        entries = [
            e for e in entries
            if datetime.fromisoformat(e.get("timestamp", "2000-01-01")) >= cutoff
        ]

    return entries[:limit]


def get_entries_summary() -> str:
    """
    Get a text summary of recent changes for AI context.

    This can be included in AI prompts so it knows what actions
    have been taken recently.
    """
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


# Action type options for UI
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
