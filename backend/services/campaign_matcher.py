"""
Campaign fuzzy matching service.

Provides autocomplete/fuzzy matching for campaign names across platforms.
"""

import json
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "connectors" / "data"


def get_all_campaigns() -> list[dict]:
    """Get all unique campaigns from Meta and Google Ads data."""
    campaigns = []
    seen = set()

    # Meta Ads campaigns
    meta_file = DATA_DIR / "meta_ads" / "campaigns_last_30d.json"
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            for row in meta_data:
                key = ("Meta Ads", row.get("campaign_id"), row.get("campaign_name"))
                if key not in seen and row.get("campaign_name"):
                    seen.add(key)
                    campaigns.append({
                        "channel": "Meta Ads",
                        "campaign_id": str(row.get("campaign_id", "")),
                        "campaign_name": row.get("campaign_name", ""),
                    })
        except (json.JSONDecodeError, IOError):
            pass

    # Google Ads campaigns
    google_file = DATA_DIR / "google_ads" / "campaigns_last_30d.json"
    if google_file.exists():
        try:
            with open(google_file, "r", encoding="utf-8") as f:
                google_data = json.load(f)
            for row in google_data:
                key = ("Google Ads", row.get("campaign_id"), row.get("campaign_name"))
                if key not in seen and row.get("campaign_name"):
                    seen.add(key)
                    campaigns.append({
                        "channel": "Google Ads",
                        "campaign_id": str(row.get("campaign_id", "")),
                        "campaign_name": row.get("campaign_name", ""),
                    })
        except (json.JSONDecodeError, IOError):
            pass

    return campaigns


def similarity_score(query: str, target: str) -> float:
    """Calculate similarity score between query and target string."""
    query_lower = query.lower()
    target_lower = target.lower()

    # Exact match
    if query_lower == target_lower:
        return 1.0

    # Contains match (high score)
    if query_lower in target_lower:
        # Longer matches within target get higher scores
        return 0.8 + (len(query_lower) / len(target_lower)) * 0.15

    # Starts with (high score)
    if target_lower.startswith(query_lower):
        return 0.9

    # Word match - if query matches any word in the target
    target_words = target_lower.split()
    query_words = query_lower.split()
    for qw in query_words:
        for tw in target_words:
            if qw in tw or tw.startswith(qw):
                return 0.7

    # Fuzzy match using SequenceMatcher
    ratio = SequenceMatcher(None, query_lower, target_lower).ratio()
    return ratio * 0.6  # Scale down pure fuzzy matches


def search_campaigns(
    query: str,
    channel: Optional[str] = None,
    limit: int = 10,
    min_score: float = 0.3,
) -> list[dict]:
    """
    Search for campaigns matching the query string.

    Args:
        query: Search string (partial campaign name)
        channel: Optional filter by channel ("Meta Ads" or "Google Ads")
        limit: Maximum results to return
        min_score: Minimum similarity score (0.0 - 1.0)

    Returns:
        List of matching campaigns with similarity scores, sorted by score
    """
    if not query or len(query) < 2:
        return []

    campaigns = get_all_campaigns()

    # Filter by channel if specified
    if channel:
        campaigns = [c for c in campaigns if c["channel"].lower() == channel.lower()]

    # Score each campaign
    results = []
    for campaign in campaigns:
        score = similarity_score(query, campaign["campaign_name"])
        if score >= min_score:
            results.append({
                **campaign,
                "score": round(score, 3),
            })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]


def find_best_match(
    query: str,
    channel: Optional[str] = None,
    min_score: float = 0.5,
) -> Optional[dict]:
    """
    Find the single best matching campaign.

    Args:
        query: Campaign name or partial name
        channel: Optional channel filter
        min_score: Minimum score to consider a match

    Returns:
        Best matching campaign or None
    """
    results = search_campaigns(query, channel=channel, limit=1, min_score=min_score)
    return results[0] if results else None
