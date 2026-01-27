"""
Metrics API endpoints.

Provides access to all marketing metrics and reports.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from services.data_loader import (
    get_latest_report,
    get_decision_signals,
    get_blended_metrics,
    get_kendall_attribution,
    get_kendall_historical,
    get_channel_campaigns,
    get_gsc_branded,
    get_shopify_metrics,
    get_google_ads_campaigns,
    get_meta_ads_campaigns,
    get_timeframe_summary,
    get_google_campaigns_for_timeframe,
    get_meta_campaigns_for_timeframe,
    get_halo_effect_trend,
    get_shipping_reminder_state,
    update_shipping_reminder,
    get_spend_outcome_correlation,
    get_channel_correlation,
    get_budget_recommendations,
    VALID_TIMEFRAMES,
)

router = APIRouter()


@router.get("/report")
async def get_report():
    """Get the latest CAM report with all summary data."""
    report = get_latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="No report data available")
    return report


@router.get("/signals")
async def get_signals():
    """Get decision signals for the action board."""
    return get_decision_signals()


@router.get("/blended")
async def get_blended():
    """Get blended metrics (NCAC, first-click, etc.)."""
    return get_blended_metrics()


@router.get("/attribution")
async def get_attribution():
    """Get full Kendall attribution data."""
    data = get_kendall_attribution()
    if not data:
        raise HTTPException(status_code=404, detail="No attribution data available")
    return data


@router.get("/historical")
async def get_historical():
    """Get historical Kendall metrics."""
    data = get_kendall_historical()
    if not data:
        raise HTTPException(status_code=404, detail="No historical data available")
    return data


@router.get("/channels/{channel}")
async def get_channel(channel: str):
    """Get campaign breakdown for a specific channel."""
    channel_map = {
        "google": "Google Ads",
        "meta": "Meta Ads",
        "klaviyo": "Klaviyo",
        "organic": "Organic",
    }

    channel_name = channel_map.get(channel.lower())
    if not channel_name:
        raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")

    campaigns = get_channel_campaigns(channel_name)
    return {"channel": channel_name, "campaigns": campaigns}


@router.get("/gsc")
async def get_gsc():
    """Get Google Search Console branded/non-branded data."""
    data = get_gsc_branded()
    if not data:
        raise HTTPException(status_code=404, detail="No GSC data available")
    return data


@router.get("/shopify")
async def get_shopify():
    """Get Shopify metrics."""
    data = get_shopify_metrics()
    if not data:
        raise HTTPException(status_code=404, detail="No Shopify data available")
    return data


@router.get("/google-ads")
async def get_google_ads():
    """Get Google Ads campaign data."""
    data = get_google_ads_campaigns()
    if not data:
        raise HTTPException(status_code=404, detail="No Google Ads data available")
    return data


@router.get("/meta-ads")
async def get_meta_ads():
    """Get Meta Ads campaign data."""
    data = get_meta_ads_campaigns()
    if not data:
        raise HTTPException(status_code=404, detail="No Meta Ads data available")
    return data


@router.get("/summary")
async def get_summary():
    """Get a quick summary of key metrics."""
    report = get_latest_report()
    if not report:
        return {
            "has_data": False,
            "message": "No data available - run daily pull first"
        }

    r = report.get("report", {})
    summary = r.get("summary", {})
    signals = get_decision_signals()

    return {
        "has_data": True,
        "generated_at": report.get("generated_at"),
        "cam_per_order": summary.get("blended_cam_per_order", 0),
        "total_orders": summary.get("total_orders", 0),
        "total_revenue": summary.get("total_revenue", 0),
        "total_ad_spend": summary.get("total_ad_spend", 0),
        "total_cam": summary.get("blended_cam", 0),
        "spend_decision": signals.get("spend_decision", "hold"),
        "campaigns_to_scale_count": len(signals.get("campaigns_to_scale", [])),
        "campaigns_to_watch_count": len(signals.get("campaigns_to_watch", [])),
        "alerts_count": len(signals.get("alerts", [])),
    }


# ============================================================================
# TIMEFRAME-BASED ENDPOINTS (for short-term analysis)
# ============================================================================

@router.get("/timeframe/{days}")
async def get_timeframe_metrics(days: int):
    """
    Get metrics for a specific timeframe (1, 2, 3, 7, 14, or 30 days).

    This endpoint is crucial for short-term analysis when sales are declining.
    It shows:
    - Summary metrics for the period
    - Comparison vs previous period
    - Problem campaigns (low ROAS, high spend)
    - Winning campaigns (high ROAS)
    - Per-channel breakdown
    """
    if days not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Valid options: {VALID_TIMEFRAMES}"
        )

    data = get_timeframe_summary(days)
    if not data.get("summary", {}).get("total_orders"):
        raise HTTPException(
            status_code=404,
            detail=f"No data available for last {days} days"
        )

    return data


@router.get("/timeframe/{days}/google")
async def get_google_timeframe(days: int):
    """Get Google Ads campaigns for a specific timeframe."""
    if days not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Valid options: {VALID_TIMEFRAMES}"
        )

    campaigns = get_google_campaigns_for_timeframe(days)
    return {
        "timeframe": days,
        "channel": "Google Ads",
        "campaigns": campaigns,
        "total_spend": sum(c.get("spend", 0) for c in campaigns),
        "total_revenue": sum(c.get("conversion_value", 0) for c in campaigns),
    }


@router.get("/timeframe/{days}/meta")
async def get_meta_timeframe(days: int):
    """Get Meta Ads campaigns for a specific timeframe."""
    if days not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Valid options: {VALID_TIMEFRAMES}"
        )

    campaigns = get_meta_campaigns_for_timeframe(days)
    return {
        "timeframe": days,
        "channel": "Meta Ads",
        "campaigns": campaigns,
        "total_spend": sum(c.get("spend", 0) for c in campaigns),
        "total_revenue": sum(c.get("purchase_value", 0) for c in campaigns),
    }


@router.get("/timeframes")
async def get_available_timeframes():
    """Get list of available timeframe options."""
    return {
        "timeframes": [
            {"days": 1, "label": "Today"},
            {"days": 2, "label": "Last 2 days"},
            {"days": 3, "label": "Last 3 days"},
            {"days": 7, "label": "Last 7 days"},
            {"days": 14, "label": "Last 14 days"},
            {"days": 30, "label": "Last 30 days"},
        ]
    }


@router.get("/halo-effect")
async def get_halo_effect(days: int = 30):
    """
    Get halo effect correlation data showing ad spend vs Amazon sales over time.

    This helps visualize whether increased marketing spend correlates with
    Amazon sales (the "halo effect" where customers see ads then buy on Amazon).

    Query params:
        days: Number of days to include (default: 30)
    """
    if days not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Valid options: {VALID_TIMEFRAMES}"
        )

    data = get_halo_effect_trend(days)
    if not data.get("data"):
        raise HTTPException(
            status_code=404,
            detail=f"No halo effect data available for last {days} days"
        )

    return data


# ============================================================================
# SIGNAL TRIANGULATION (Spend-to-Outcome Correlation)
# ============================================================================

@router.get("/correlation")
async def get_correlation(days: int = 14):
    """
    Get spend-to-outcome correlation analysis.

    This is the core triangulation endpoint - it doesn't trust any attribution model.
    Instead, it answers: "When spend changed, what happened to actual sales?"

    Query params:
        days: Comparison period (default: 14 days current vs 14 days prior)
    """
    valid_days = [7, 14, 30]
    if days not in valid_days:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Valid options: {valid_days}"
        )

    data = get_spend_outcome_correlation(days)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])

    return data


@router.get("/correlation/channels")
async def get_correlation_by_channel(days: int = 14):
    """
    Get spend-to-outcome correlation broken down by channel.

    Shows which platform (Google vs Meta) has better correlation
    between spend changes and business outcomes.
    """
    valid_days = [7, 14, 30]
    if days not in valid_days:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Valid options: {valid_days}"
        )

    data = get_channel_correlation(days)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])

    return data


@router.get("/recommendations")
async def get_recommendations(days: int = 7):
    """
    Get actionable budget recommendations based on triangulation data.

    Synthesizes signal triangulation, efficiency metrics, and campaign performance
    into specific budget recommendations with dollar amounts.

    Query params:
        days: Analysis period (default: 7 days)
    """
    valid_days = [7, 14, 30]
    if days not in valid_days:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Valid options: {valid_days}"
        )

    data = get_budget_recommendations(days)
    if "error" in data and not data.get("recommendations"):
        raise HTTPException(status_code=404, detail=data["error"])

    return data


# ============================================================================
# OPERATIONAL REMINDERS
# ============================================================================

@router.get("/shipping-reminder")
async def get_shipping_reminder():
    """Get the current shipping cost reminder state."""
    return get_shipping_reminder_state()


@router.post("/shipping-reminder/acknowledge")
async def acknowledge_shipping_reminder(kendall_setting: float = None):
    """
    Acknowledge the shipping cost reminder, resetting the 60-day timer.

    Optionally update the Kendall setting value that's being tracked.
    """
    state = update_shipping_reminder(kendall_setting=kendall_setting)
    return {
        "success": True,
        "message": "Shipping reminder acknowledged. Next reminder in 60 days.",
        "state": state,
    }
