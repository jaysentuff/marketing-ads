"""
AI Recommendation Tracking Service.

Tracks AI-generated recommendations, their status (done/ignored/partial),
and the outcomes after actions are taken. This creates the feedback loop
the LLM needs to learn from past decisions.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Literal
from zoneinfo import ZoneInfo

from services.data_loader import get_kendall_historical, get_date_cutoff

EST = ZoneInfo("America/New_York")

RECOMMENDATIONS_FILE = Path(__file__).parent.parent.parent / "connectors" / "data" / "ai_recommendations.json"


RecommendationStatus = Literal["pending", "done", "ignored", "partial"]
OutcomeStatus = Literal["pending", "positive", "negative", "neutral", "unknown"]


def load_recommendations() -> list[dict]:
    """Load all AI recommendations from file."""
    try:
        with open(RECOMMENDATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_recommendations(recommendations: list[dict]):
    """Save recommendations to file."""
    RECOMMENDATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RECOMMENDATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(recommendations, f, indent=2, default=str)


def generate_recommendation_id() -> str:
    """Generate a unique recommendation ID."""
    now = datetime.now(EST)
    return f"rec_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond}"


def add_recommendation(
    recommendation_type: str,
    action: str,
    channel: Optional[str] = None,
    campaign: Optional[str] = None,
    campaign_id: Optional[str] = None,
    budget_change_amount: Optional[float] = None,
    budget_change_percent: Optional[float] = None,
    reason: str = "",
    confidence: str = "medium",
    signals_used: Optional[list[str]] = None,
    metrics_at_recommendation: Optional[dict] = None,
    llm_reasoning: Optional[str] = None,
) -> dict:
    """
    Add a new AI recommendation.

    Args:
        recommendation_type: Type of recommendation (scale, cut, hold, shift, etc.)
        action: Human-readable action description
        channel: Google Ads, Meta Ads, etc.
        campaign: Campaign name if campaign-specific
        campaign_id: Campaign ID for precise matching
        budget_change_amount: Dollar amount change recommended
        budget_change_percent: Percentage change recommended
        reason: Why this recommendation was made
        confidence: high, medium, low
        signals_used: List of signals that informed this recommendation
        metrics_at_recommendation: Snapshot of key metrics when recommendation was made
        llm_reasoning: Full LLM reasoning text for this recommendation

    Returns:
        The created recommendation record
    """
    recommendations = load_recommendations()

    now = datetime.now(EST)
    rec_id = generate_recommendation_id()

    recommendation = {
        "id": rec_id,
        "created_at": now.isoformat(),
        "recommendation_type": recommendation_type,
        "action": action,
        "channel": channel,
        "campaign": campaign,
        "campaign_id": campaign_id,
        "budget_change_amount": budget_change_amount,
        "budget_change_percent": budget_change_percent,
        "reason": reason,
        "confidence": confidence,
        "signals_used": signals_used or [],
        "metrics_at_recommendation": metrics_at_recommendation or {},
        "llm_reasoning": llm_reasoning,

        # Status tracking
        "status": "pending",  # pending, done, ignored, partial
        "status_updated_at": None,
        "action_taken": None,  # What the user actually did
        "reason_not_followed": None,  # If ignored/partial, why

        # Outcome tracking (populated later)
        "metrics_after_7d": None,
        "metrics_after_14d": None,
        "outcome": "pending",  # pending, positive, negative, neutral, unknown
        "outcome_notes": None,
    }

    recommendations.append(recommendation)
    save_recommendations(recommendations)

    return recommendation


def update_recommendation_status(
    recommendation_id: str,
    status: RecommendationStatus,
    action_taken: Optional[str] = None,
    reason_not_followed: Optional[str] = None,
) -> Optional[dict]:
    """
    Update the status of a recommendation.

    Called when user acts on (or ignores) a recommendation.
    """
    recommendations = load_recommendations()

    for rec in recommendations:
        if rec["id"] == recommendation_id:
            rec["status"] = status
            rec["status_updated_at"] = datetime.now(EST).isoformat()
            if action_taken:
                rec["action_taken"] = action_taken
            if reason_not_followed:
                rec["reason_not_followed"] = reason_not_followed

            save_recommendations(recommendations)
            return rec

    return None


def record_outcome(
    recommendation_id: str,
    metrics_after: dict,
    days_after: int = 7,
) -> Optional[dict]:
    """
    Record metrics after a recommendation was acted upon.

    This should be called by a scheduled job 7 and 14 days after
    recommendations are acted upon.
    """
    recommendations = load_recommendations()

    for rec in recommendations:
        if rec["id"] == recommendation_id:
            field = f"metrics_after_{days_after}d"
            rec[field] = metrics_after

            # Calculate outcome if we have 7-day data
            if days_after == 7 and rec["metrics_at_recommendation"]:
                rec["outcome"] = _calculate_outcome(
                    rec["metrics_at_recommendation"],
                    metrics_after,
                    rec["recommendation_type"]
                )

            save_recommendations(recommendations)
            return rec

    return None


def _calculate_outcome(
    before: dict,
    after: dict,
    recommendation_type: str
) -> OutcomeStatus:
    """
    Calculate whether a recommendation had positive, negative, or neutral outcome.

    This uses multiple signals to determine success:
    - MER change (higher is better)
    - NCAC change (lower is better)
    - Revenue change
    - CAM change
    """
    mer_before = before.get("mer", 0)
    mer_after = after.get("mer", 0)
    ncac_before = before.get("ncac", 0)
    ncac_after = after.get("ncac", 0)
    cam_before = before.get("cam_per_order", 0)
    cam_after = after.get("cam_per_order", 0)

    # Calculate directional changes
    mer_improved = mer_after > mer_before * 1.05  # 5% improvement
    mer_declined = mer_after < mer_before * 0.95
    ncac_improved = ncac_after < ncac_before * 0.95  # 5% improvement (lower is better)
    ncac_worsened = ncac_after > ncac_before * 1.05
    cam_improved = cam_after > cam_before * 1.05
    cam_declined = cam_after < cam_before * 0.95

    # Score the outcome
    positive_signals = sum([mer_improved, ncac_improved, cam_improved])
    negative_signals = sum([mer_declined, ncac_worsened, cam_declined])

    if positive_signals >= 2 and negative_signals == 0:
        return "positive"
    elif negative_signals >= 2 and positive_signals == 0:
        return "negative"
    elif positive_signals > negative_signals:
        return "positive"
    elif negative_signals > positive_signals:
        return "negative"
    else:
        return "neutral"


def get_pending_recommendations(days: int = 7) -> list[dict]:
    """Get recommendations that haven't been acted on yet."""
    recommendations = load_recommendations()
    cutoff = datetime.now(EST) - timedelta(days=days)

    pending = []
    for rec in recommendations:
        created = datetime.fromisoformat(rec["created_at"])
        if rec["status"] == "pending" and created >= cutoff:
            pending.append(rec)

    return sorted(pending, key=lambda x: x["created_at"], reverse=True)


def get_recent_recommendations(days: int = 30, limit: int = 50) -> list[dict]:
    """Get recent recommendations with their outcomes."""
    recommendations = load_recommendations()
    cutoff = datetime.now(EST) - timedelta(days=days)

    recent = []
    for rec in recommendations:
        try:
            created = datetime.fromisoformat(rec["created_at"])
            if created >= cutoff:
                recent.append(rec)
        except (ValueError, TypeError):
            continue

    recent.sort(key=lambda x: x["created_at"], reverse=True)
    return recent[:limit]


def get_recommendations_needing_outcome_check() -> list[dict]:
    """
    Get recommendations that were acted upon and need outcome measurement.

    Returns recommendations where:
    - Status is 'done' or 'partial'
    - Action was taken 7+ days ago
    - metrics_after_7d is not yet recorded
    """
    recommendations = load_recommendations()
    now = datetime.now(EST)

    needing_check = []
    for rec in recommendations:
        if rec["status"] not in ["done", "partial"]:
            continue
        if rec.get("metrics_after_7d") is not None:
            continue

        status_updated = rec.get("status_updated_at")
        if not status_updated:
            continue

        try:
            updated_date = datetime.fromisoformat(status_updated)
            days_since = (now - updated_date).days
            if days_since >= 7:
                rec["days_since_action"] = days_since
                needing_check.append(rec)
        except (ValueError, TypeError):
            continue

    return needing_check


def get_recommendation_summary_for_llm(days: int = 30) -> dict:
    """
    Get a summary of past recommendations and outcomes for LLM context.

    This is the key feedback that helps the LLM learn from past decisions.
    """
    recommendations = get_recent_recommendations(days=days, limit=100)

    if not recommendations:
        return {
            "summary": "No previous recommendations recorded.",
            "recommendations": [],
            "patterns": {},
        }

    # Count outcomes by type
    outcomes_by_type = {}
    outcomes_by_channel = {}

    for rec in recommendations:
        rec_type = rec.get("recommendation_type", "unknown")
        channel = rec.get("channel", "unknown")
        outcome = rec.get("outcome", "pending")
        status = rec.get("status", "pending")

        # Track by type
        if rec_type not in outcomes_by_type:
            outcomes_by_type[rec_type] = {"done": 0, "ignored": 0, "positive": 0, "negative": 0, "neutral": 0}
        if status in ["done", "partial"]:
            outcomes_by_type[rec_type]["done"] += 1
        elif status == "ignored":
            outcomes_by_type[rec_type]["ignored"] += 1
        if outcome in ["positive", "negative", "neutral"]:
            outcomes_by_type[rec_type][outcome] += 1

        # Track by channel
        if channel not in outcomes_by_channel:
            outcomes_by_channel[channel] = {"done": 0, "ignored": 0, "positive": 0, "negative": 0}
        if status in ["done", "partial"]:
            outcomes_by_channel[channel]["done"] += 1
        if outcome == "positive":
            outcomes_by_channel[channel]["positive"] += 1
        elif outcome == "negative":
            outcomes_by_channel[channel]["negative"] += 1

    # Identify patterns
    patterns = []

    for rec_type, counts in outcomes_by_type.items():
        if counts["done"] >= 3:
            success_rate = counts["positive"] / counts["done"] if counts["done"] > 0 else 0
            if success_rate >= 0.7:
                patterns.append(f"'{rec_type}' recommendations have been successful ({counts['positive']}/{counts['done']} positive outcomes)")
            elif success_rate <= 0.3 and counts["negative"] >= 2:
                patterns.append(f"'{rec_type}' recommendations have often backfired ({counts['negative']}/{counts['done']} negative outcomes)")

    # Get specific examples of what worked and what didn't
    successful = [r for r in recommendations if r.get("outcome") == "positive" and r.get("status") in ["done", "partial"]]
    failed = [r for r in recommendations if r.get("outcome") == "negative" and r.get("status") in ["done", "partial"]]
    ignored = [r for r in recommendations if r.get("status") == "ignored"]

    # Build summary text for LLM
    summary_parts = [f"Summary of {len(recommendations)} recommendations in last {days} days:"]

    done_count = sum(1 for r in recommendations if r.get("status") in ["done", "partial"])
    ignored_count = sum(1 for r in recommendations if r.get("status") == "ignored")
    pending_count = sum(1 for r in recommendations if r.get("status") == "pending")

    summary_parts.append(f"- {done_count} acted upon, {ignored_count} ignored, {pending_count} still pending")

    if successful:
        summary_parts.append(f"- {len(successful)} had positive outcomes")
    if failed:
        summary_parts.append(f"- {len(failed)} had negative outcomes (learn from these)")

    if patterns:
        summary_parts.append("Observed patterns:")
        for p in patterns:
            summary_parts.append(f"  - {p}")

    # Include specific examples
    examples = []

    for rec in successful[:3]:
        examples.append({
            "type": "success",
            "recommendation": rec.get("action"),
            "channel": rec.get("channel"),
            "reason": rec.get("reason"),
            "outcome": "positive",
            "metrics_change": _describe_metrics_change(
                rec.get("metrics_at_recommendation", {}),
                rec.get("metrics_after_7d", {})
            )
        })

    for rec in failed[:3]:
        examples.append({
            "type": "failure",
            "recommendation": rec.get("action"),
            "channel": rec.get("channel"),
            "reason": rec.get("reason"),
            "outcome": "negative",
            "metrics_change": _describe_metrics_change(
                rec.get("metrics_at_recommendation", {}),
                rec.get("metrics_after_7d", {})
            )
        })

    for rec in ignored[:2]:
        examples.append({
            "type": "ignored",
            "recommendation": rec.get("action"),
            "channel": rec.get("channel"),
            "reason_ignored": rec.get("reason_not_followed", "No reason provided"),
        })

    return {
        "summary": "\n".join(summary_parts),
        "total_recommendations": len(recommendations),
        "acted_upon": done_count,
        "ignored": ignored_count,
        "outcomes": {
            "positive": len(successful),
            "negative": len(failed),
            "neutral": sum(1 for r in recommendations if r.get("outcome") == "neutral"),
            "pending": sum(1 for r in recommendations if r.get("outcome") == "pending"),
        },
        "by_type": outcomes_by_type,
        "by_channel": outcomes_by_channel,
        "patterns": patterns,
        "examples": examples,
        "recommendations": recommendations,
    }


def _describe_metrics_change(before: dict, after: dict) -> str:
    """Describe the change in metrics between two snapshots."""
    if not before or not after:
        return "No metrics comparison available"

    changes = []

    mer_before = before.get("mer", 0)
    mer_after = after.get("mer", 0)
    if mer_before > 0:
        mer_change = ((mer_after - mer_before) / mer_before) * 100
        changes.append(f"MER {mer_change:+.1f}%")

    ncac_before = before.get("ncac", 0)
    ncac_after = after.get("ncac", 0)
    if ncac_before > 0:
        ncac_change = ((ncac_after - ncac_before) / ncac_before) * 100
        changes.append(f"NCAC {ncac_change:+.1f}%")

    cam_before = before.get("cam_per_order", 0)
    cam_after = after.get("cam_per_order", 0)
    if cam_before > 0:
        cam_change = ((cam_after - cam_before) / cam_before) * 100
        changes.append(f"CAM/order {cam_change:+.1f}%")

    return ", ".join(changes) if changes else "No significant changes"


def link_changelog_to_recommendation(
    changelog_entry_id: int,
    recommendation_id: str,
) -> bool:
    """
    Link a changelog entry to a recommendation.

    This is called when a user completes an action that was recommended by AI.
    """
    recommendations = load_recommendations()

    for rec in recommendations:
        if rec["id"] == recommendation_id:
            if "linked_changelog_entries" not in rec:
                rec["linked_changelog_entries"] = []
            rec["linked_changelog_entries"].append(changelog_entry_id)
            rec["status"] = "done"
            rec["status_updated_at"] = datetime.now(EST).isoformat()
            save_recommendations(recommendations)
            return True

    return False
