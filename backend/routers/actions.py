"""
Actions API endpoints.

Provides action items for the Action Board with budget recommendations.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from services.data_loader import (
    get_latest_report,
    get_decision_signals,
    get_kendall_attribution,
)
from services.changelog import add_entry, get_recent_entries

router = APIRouter()


class ActionItem(BaseModel):
    """A single action item with budget recommendation."""
    id: str
    priority: str  # HIGH, MEDIUM, LOW
    action_type: str
    action: str
    campaign: str
    channel: str
    reason: str
    budget_change: str
    budget_amount: float
    budget_percent: float
    new_budget: str
    icon: str


class CompletedAction(BaseModel):
    """Request body for completing an action."""
    id: str
    action_type: str
    campaign: str
    channel: str
    budget_amount: float
    budget_percent: float
    reason: str


class CompletedActionsRequest(BaseModel):
    """Request body for completing multiple actions."""
    actions: list[CompletedAction]


def calculate_budget_recommendation(current_spend: float, roas: float, action_type: str) -> dict:
    """Calculate specific budget change recommendation."""
    if action_type == "scale":
        if roas >= 4.0:
            pct = 25
        elif roas >= 3.5:
            pct = 20
        else:
            pct = 15
        change = current_spend * (pct / 100)
        return {
            "percent": pct,
            "amount": change,
            "new_budget": current_spend + change,
            "direction": "increase"
        }
    else:  # cut
        if roas < 1.0:
            pct = 30
        elif roas < 1.5:
            pct = 25
        else:
            pct = 20
        change = current_spend * (pct / 100)
        return {
            "percent": pct,
            "amount": change,
            "new_budget": current_spend - change,
            "direction": "decrease"
        }


def get_campaign_spend(channel: str, campaign_name: str) -> float:
    """Get average daily campaign spend from actual spend data."""
    import json
    import os
    from pathlib import Path

    data_dir = Path(__file__).parent.parent.parent / "connectors" / "data"

    # Try to get actual spend data from campaign files
    if "meta" in channel.lower():
        campaign_file = data_dir / "meta_ads" / "campaigns_last_30d.json"
    else:
        campaign_file = data_dir / "google_ads" / "campaigns_last_30d.json"

    try:
        if campaign_file.exists():
            with open(campaign_file) as f:
                campaigns = json.load(f)

            # Find all entries for this campaign and calculate average daily spend
            daily_spends = []
            for entry in campaigns:
                name = entry.get("campaign_name") or entry.get("name", "")
                if campaign_name in name or name in campaign_name:
                    spend = entry.get("spend", 0)
                    if spend > 0:
                        daily_spends.append(spend)

            if daily_spends:
                # Return average daily spend
                return sum(daily_spends) / len(daily_spends)
    except Exception:
        pass

    # Fallback to attribution data estimate
    attribution = get_kendall_attribution()
    if attribution:
        channel_data = attribution.get(channel, {})
        breakdowns = channel_data.get("breakdowns", {})
        campaign_data = breakdowns.get(campaign_name, {})
        revenue = campaign_data.get("sales", 0)
        roas = campaign_data.get("roas", 2)
        if roas > 0 and revenue > 0:
            return revenue / roas / 30

    return 50  # Default fallback


def get_recently_actioned_campaigns(days: int = 7) -> set:
    """Get campaign names that have been actioned recently."""
    entries = get_recent_entries(days=days, limit=100)
    actioned = set()
    for entry in entries:
        campaign = entry.get("campaign", "")
        if campaign:
            # Store partial matches to handle ID variations
            actioned.add(campaign)
            # Also add just the name without ID for matching
            if "(ID:" in campaign:
                name_only = campaign.split("(ID:")[0].strip()
                actioned.add(name_only)
    return actioned


@router.get("/list")
async def get_action_items():
    """Get all action items with budget recommendations."""
    report = get_latest_report()
    if not report:
        return {"actions": [], "summary": None}

    signals = get_decision_signals()
    r = report.get("report", {})
    summary = r.get("summary", {})

    # Get recently actioned campaigns to filter out
    actioned_campaigns = get_recently_actioned_campaigns(days=7)

    def is_already_actioned(campaign_name: str) -> bool:
        """Check if a campaign has already been actioned."""
        if campaign_name in actioned_campaigns:
            return True
        # Check partial match (name without ID)
        if "(ID:" in campaign_name:
            name_only = campaign_name.split("(ID:")[0].strip()
            if name_only in actioned_campaigns:
                return True
        # Check if any actioned campaign contains this name
        for actioned in actioned_campaigns:
            if campaign_name in actioned or actioned in campaign_name:
                return True
        return False

    actions = []
    action_id = 0

    # Campaigns to SCALE (filter out already actioned)
    for c in signals.get("campaigns_to_scale", [])[:5]:
        if is_already_actioned(c["name"]):
            continue  # Skip already actioned campaigns
        daily_spend = get_campaign_spend(c["channel"], c["name"])
        rec = calculate_budget_recommendation(daily_spend, c["roas"], "scale")

        action_id += 1
        actions.append({
            "id": f"scale_{action_id}",
            "priority": "HIGH",
            "action_type": "spend_increase",
            "action": f"INCREASE: {c['name'][:45]}",
            "campaign": c["name"],
            "channel": c["channel"],
            "reason": f"{c['roas']:.1f}x ROAS | {c['orders']} orders | {c.get('nc_pct', 0)*100:.0f}% new customers",
            "budget_change": f"+${rec['amount']:.0f}/day (+{rec['percent']}%)",
            "budget_amount": rec['amount'],
            "budget_percent": rec['percent'],
            "new_budget": f"Avg: ${daily_spend:.0f} -> ${rec['new_budget']:.0f}/day",
            "icon": "TrendingUp"
        })

    # Campaigns to CUT (filter out already actioned)
    for c in signals.get("campaigns_to_watch", [])[:5]:
        if is_already_actioned(c["name"]):
            continue  # Skip already actioned campaigns

        daily_spend = get_campaign_spend(c["channel"], c["name"])
        rec = calculate_budget_recommendation(daily_spend, c["roas"], "cut")

        action_id += 1
        actions.append({
            "id": f"cut_{action_id}",
            "priority": "MEDIUM",
            "action_type": "spend_decrease",
            "action": f"DECREASE: {c['name'][:45]}",
            "campaign": c["name"],
            "channel": c["channel"],
            "reason": f"Only {c['roas']:.1f}x ROAS | {c['orders']} orders | {c.get('note', 'Underperforming')}",
            "budget_change": f"-${rec['amount']:.0f}/day (-{rec['percent']}%)",
            "budget_amount": -rec['amount'],
            "budget_percent": -rec['percent'],
            "new_budget": f"Avg: ${daily_spend:.0f} -> ${rec['new_budget']:.0f}/day",
            "icon": "TrendingDown"
        })

    # Channel shift
    shift = signals.get("channel_shift")
    if shift:
        action_id += 1
        shift_amount = summary.get("total_ad_spend", 10000) * 0.10 / 30
        actions.append({
            "id": f"shift_{action_id}",
            "priority": "MEDIUM",
            "action_type": "budget_shift",
            "action": f"SHIFT BUDGET: {shift['from']} → {shift['to']}",
            "campaign": f"{shift['from']} to {shift['to']}",
            "channel": "Cross-Channel",
            "reason": shift['reason'],
            "budget_change": f"Move ${shift_amount:.0f}/day",
            "budget_amount": shift_amount,
            "budget_percent": 10,
            "new_budget": "",
            "icon": "ArrowRightLeft"
        })

    # TOF actions (only show if not recently actioned)
    tof = signals.get("tof_assessment")
    if tof and not is_already_actioned("TOF Prospecting"):
        verdict = tof.get("verdict", "")
        if verdict == "needs_review":
            action_id += 1
            actions.append({
                "id": f"tof_{action_id}",
                "priority": "LOW",
                "action_type": "other",
                "action": "REVIEW TOF Campaigns (Don't cut yet!)",
                "campaign": "TOF Prospecting",
                "channel": "Meta Ads",
                "reason": f"NCAC ${tof.get('ncac_7d_avg', 0):.0f} | Branded search {tof.get('branded_search_pct', 0):.0f}%",
                "budget_change": "No change yet",
                "budget_amount": 0,
                "budget_percent": 0,
                "new_budget": "Pending review",
                "icon": "Search"
            })
        elif verdict == "healthy":
            action_id += 1
            actions.append({
                "id": f"tof_{action_id}",
                "priority": "LOW",
                "action_type": "spend_increase",
                "action": "MAINTAIN/TEST TOF (It's working!)",
                "campaign": "TOF Prospecting",
                "channel": "Meta Ads",
                "reason": f"NCAC ${tof.get('ncac_7d_avg', 0):.0f} (under $50 target) | Test small increase",
                "budget_change": "+$20/day (test)",
                "budget_amount": 20,
                "budget_percent": 10,
                "new_budget": "",
                "icon": "CheckCircle"
            })

    return {
        "actions": actions,
        "summary": {
            "cam_per_order": summary.get("blended_cam_per_order", 0),
            "total_orders": summary.get("total_orders", 0),
            "total_ad_spend": summary.get("total_ad_spend", 0),
            "spend_decision": signals.get("spend_decision", "hold"),
        },
        "generated_at": report.get("generated_at"),
    }


@router.post("/complete")
async def complete_actions(request: CompletedActionsRequest):
    """Log completed actions to the changelog."""
    report = get_latest_report()
    summary = report.get("report", {}).get("summary", {}) if report else {}

    metrics_snapshot = {
        "cam_per_order": summary.get("blended_cam_per_order", 0),
        "total_orders": summary.get("total_orders", 0),
        "total_ad_spend": summary.get("total_ad_spend", 0),
        "total_cam": summary.get("blended_cam", 0),
    }

    logged_entries = []

    for action in request.actions:
        if action.budget_amount != 0:
            if action.budget_amount > 0:
                desc = f"Increased budget +${abs(action.budget_amount):.0f}/day (+{abs(action.budget_percent)}%)"
            else:
                desc = f"Decreased budget -${abs(action.budget_amount):.0f}/day (-{abs(action.budget_percent)}%)"
        else:
            desc = f"Reviewed: {action.campaign}"

        entry = add_entry(
            action_type=action.action_type,
            description=desc,
            channel=action.channel,
            campaign=action.campaign,
            amount=abs(action.budget_amount) if action.budget_amount != 0 else None,
            percent_change=abs(action.budget_percent) if action.budget_percent != 0 else None,
            notes=f"Action Board recommendation. Reason: {action.reason[:100]}",
            metrics_snapshot=metrics_snapshot,
        )
        logged_entries.append(entry)

    return {
        "success": True,
        "logged_count": len(logged_entries),
        "entries": logged_entries,
    }
