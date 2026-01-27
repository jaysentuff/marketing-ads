"""
Data loading utilities for the TuffWraps Dashboard.

Reads JSON files from the connectors/data directory.

IMPORTANT: TOF (Top-of-Funnel) campaigns should NOT be evaluated by direct ROAS.
TOF value is measured through:
1. First-click attribution (facebook_fc, google_fc from Kendall)
2. Branded search trend correlation
3. Blended new customer metrics (NCAC)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any


# Data directory path
DATA_DIR = Path(__file__).parent.parent / "connectors" / "data"

# Keywords that identify TOF campaigns (case-insensitive)
TOF_KEYWORDS = ["tof", "prospecting", "awareness", "top of funnel", "cold", "discovery"]


def is_tof_campaign(campaign_name: str) -> bool:
    """Check if a campaign is a TOF (Top-of-Funnel) campaign."""
    name_lower = campaign_name.lower()
    return any(kw in name_lower for kw in TOF_KEYWORDS)


def load_json(filepath: Path) -> dict | list | None:
    """Load a JSON file, returning None if not found."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def get_latest_report() -> dict | None:
    """Get the latest CAM report."""
    return load_json(DATA_DIR / "aggregated" / "latest_report.json")


def get_kendall_attribution() -> dict | None:
    """Get Kendall attribution by source data."""
    return load_json(DATA_DIR / "kendall" / "attribution_by_source.json")


def get_kendall_pnl() -> dict | None:
    """Get Kendall profit/loss data."""
    return load_json(DATA_DIR / "kendall" / "profit_loss.json")


def get_kendall_historical() -> dict | None:
    """
    Get Kendall historical metrics including first-click attribution.

    Key metrics:
    - facebook_fc: Meta first-click revenue
    - google_fc: Google first-click revenue
    - ncac: New Customer Acquisition Cost
    - nc_mer: New Customer MER (blended ROAS for new customers)
    - contrib_after_mkt: Contribution After Marketing (CAM)
    - amz_us_sales: Amazon US sales
    """
    return load_json(DATA_DIR / "kendall" / "historical_metrics.json")


def get_gsc_branded() -> dict | None:
    """Get Google Search Console branded vs non-branded data."""
    return load_json(DATA_DIR / "gsc" / "branded_vs_nonbranded.json")


def get_gsc_daily_trend() -> list | None:
    """Get GSC daily branded search trend."""
    return load_json(DATA_DIR / "gsc" / "daily_branded_trend.json")


def get_shopify_metrics() -> dict | None:
    """Get Shopify metrics."""
    return load_json(DATA_DIR / "shopify" / "metrics_last_30d.json")


def get_google_ads_campaigns() -> list | None:
    """Get Google Ads campaign data."""
    return load_json(DATA_DIR / "google_ads" / "campaigns_last_30d.json")


def get_meta_ads_campaigns() -> list | None:
    """Get Meta Ads campaign data."""
    return load_json(DATA_DIR / "meta_ads" / "campaigns_last_30d.json")


def get_ga4_summary() -> dict | None:
    """Get GA4 summary data."""
    return load_json(DATA_DIR / "ga4" / "summary_last_30d.json")


def get_ga4_traffic() -> list | None:
    """Get GA4 daily traffic data."""
    return load_json(DATA_DIR / "ga4" / "daily_traffic.json")


def get_klaviyo_summary() -> dict | None:
    """Get Klaviyo summary data."""
    return load_json(DATA_DIR / "klaviyo" / "summary_last_30d.json")


def format_currency(value: float) -> str:
    """Format a number as currency."""
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def format_percent(value: float, decimals: int = 1) -> str:
    """Format a number as percentage."""
    return f"{value:.{decimals}f}%"


def calculate_trend(current: float, previous: float) -> tuple[float, str]:
    """
    Calculate trend percentage and direction.
    Returns (percent_change, direction) where direction is 'up', 'down', or 'flat'.
    """
    if previous == 0:
        return 0, "flat"

    change = ((current - previous) / previous) * 100

    if change > 1:
        return change, "up"
    elif change < -1:
        return change, "down"
    return change, "flat"


def get_channel_campaigns(channel: str) -> list[dict]:
    """
    Get campaign breakdown for a specific channel from Kendall attribution.

    Args:
        channel: 'Google Ads', 'Meta Ads', 'Klaviyo', or 'Organic'

    Returns:
        List of campaign dictionaries with performance metrics.
    """
    attribution = get_kendall_attribution()
    if not attribution:
        return []

    channel_data = attribution.get(channel, {})
    breakdowns = channel_data.get("breakdowns", {})

    campaigns = []
    for name, metrics in breakdowns.items():
        campaigns.append({
            "name": name,
            "orders": metrics.get("orders", 0),
            "revenue": metrics.get("sales", 0),
            "nc_orders": metrics.get("nc_orders", 0),
            "nc_revenue": metrics.get("nc_sales", 0),
            "nc_pct": metrics.get("nc_pct", 0),
            "roas": metrics.get("roas", 0),
            "nc_roas": metrics.get("nc_roas", 0),
        })

    # Sort by orders descending
    campaigns.sort(key=lambda x: x["orders"], reverse=True)
    return campaigns


def get_blended_metrics() -> dict:
    """
    Get blended metrics from Kendall historical data.

    Returns metrics that should be used for TOF evaluation:
    - ncac: New Customer Acquisition Cost
    - meta_first_click: First-click revenue attributed to Meta
    - google_first_click: First-click revenue attributed to Google
    - branded_search_trend: Recent trend in branded search
    - amazon_sales: Amazon US sales (halo effect)
    """
    historical = get_kendall_historical()
    if not historical:
        return {}

    metrics_list = historical.get("metrics", [])
    if not metrics_list:
        return {}

    # Get last 7 days for recent performance
    recent = metrics_list[-7:] if len(metrics_list) >= 7 else metrics_list
    prior = metrics_list[-14:-7] if len(metrics_list) >= 14 else []

    # Calculate averages
    recent_ncac = sum(m.get("ncac", 0) for m in recent) / len(recent) if recent else 0
    recent_meta_fc = sum(m.get("facebook_fc", 0) for m in recent)
    recent_google_fc = sum(m.get("google_fc", 0) for m in recent)
    recent_amazon = sum(m.get("amz_us_sales", 0) for m in recent)

    prior_meta_fc = sum(m.get("facebook_fc", 0) for m in prior) if prior else 0
    prior_amazon = sum(m.get("amz_us_sales", 0) for m in prior) if prior else 0

    # Calculate trends
    meta_fc_trend = ((recent_meta_fc - prior_meta_fc) / prior_meta_fc * 100) if prior_meta_fc > 0 else 0
    amazon_trend = ((recent_amazon - prior_amazon) / prior_amazon * 100) if prior_amazon > 0 else 0

    return {
        "ncac_7d_avg": recent_ncac,
        "meta_first_click_7d": recent_meta_fc,
        "google_first_click_7d": recent_google_fc,
        "meta_fc_trend_wow": meta_fc_trend,
        "amazon_sales_7d": recent_amazon,
        "amazon_trend_wow": amazon_trend,
    }


def get_decision_signals() -> dict:
    """
    Analyze current data and return decision signals.

    IMPORTANT: TOF campaigns are evaluated DIFFERENTLY:
    - NOT by direct ROAS (which will look bad)
    - BY: First-click attribution, branded search correlation, blended NCAC

    Returns dict with:
    - spend_decision: 'increase', 'hold', or 'decrease'
    - channel_shift: suggested budget shift
    - campaigns_to_scale: list of direct-response campaigns to scale
    - campaigns_to_watch: list of campaigns needing attention
    - tof_assessment: TOF-specific evaluation
    - alerts: list of alert messages
    """
    report = get_latest_report()
    if not report:
        return {
            "spend_decision": "hold",
            "channel_shift": None,
            "campaigns_to_scale": [],
            "campaigns_to_watch": [],
            "tof_assessment": None,
            "alerts": ["No data available - run daily pull first"],
        }

    r = report.get("report", {})
    summary = r.get("summary", {})
    channels = r.get("channels", {})

    signals = {
        "spend_decision": "hold",
        "channel_shift": None,
        "campaigns_to_scale": [],
        "campaigns_to_watch": [],
        "tof_assessment": None,
        "alerts": [],
    }

    # Get blended metrics for TOF evaluation
    blended = get_blended_metrics()

    # Decision 1: Total spend based on blended CAM
    cam_per_order = summary.get("blended_cam_per_order", 0)
    target_cam = 20  # Target CAM per order

    if cam_per_order > target_cam * 1.2:  # 20% above target
        signals["spend_decision"] = "increase"
    elif cam_per_order < target_cam * 0.8:  # 20% below target
        signals["spend_decision"] = "decrease"

    # Decision 2: Channel budget shift (based on overall channel CAM, not individual campaigns)
    google_cam = channels.get("google_ads", {}).get("cam", 0)
    meta_cam = channels.get("meta_ads", {}).get("cam", 0)

    # DON'T recommend shifting away from Meta based solely on CAM
    # because Meta TOF drives Google branded search
    # Only recommend shift if one channel is drastically underperforming

    # Campaign-level decisions
    attribution = get_kendall_attribution()
    tof_campaigns = []

    if attribution:
        for channel in ["Google Ads", "Meta Ads"]:
            channel_data = attribution.get(channel, {})
            breakdowns = channel_data.get("breakdowns", {})

            for name, metrics in breakdowns.items():
                orders = metrics.get("orders", 0)
                roas = metrics.get("roas", 0)
                nc_pct = metrics.get("nc_pct", 0)

                # Check if this is a TOF campaign
                if is_tof_campaign(name):
                    tof_campaigns.append({
                        "channel": channel,
                        "name": name,
                        "orders": orders,
                        "revenue": metrics.get("sales", 0),
                        "roas": roas,
                        "nc_pct": nc_pct,
                    })
                    # DON'T evaluate TOF by direct ROAS - skip the normal logic
                    continue

                # For NON-TOF (direct response) campaigns, use ROAS-based rules
                if orders >= 10:  # Minimum volume threshold
                    if roas >= 3.0:
                        signals["campaigns_to_scale"].append({
                            "channel": channel,
                            "name": name,
                            "roas": roas,
                            "orders": orders,
                            "nc_pct": nc_pct,
                        })
                    elif roas > 0 and roas < 1.5 and orders >= 30:
                        # Only flag non-TOF campaigns with consistently low ROAS
                        signals["campaigns_to_watch"].append({
                            "channel": channel,
                            "name": name,
                            "roas": roas,
                            "orders": orders,
                            "note": "Low ROAS - review creative and targeting"
                        })

    # TOF Assessment - use different metrics
    if tof_campaigns or blended.get("meta_first_click_7d"):
        branded = r.get("branded_search", {})
        branded_pct = branded.get("branded_pct", 0)

        tof_total_orders = sum(c["orders"] for c in tof_campaigns)
        tof_total_revenue = sum(c["revenue"] for c in tof_campaigns)
        tof_avg_nc_pct = (sum(c["nc_pct"] for c in tof_campaigns) / len(tof_campaigns) * 100) if tof_campaigns else 0

        # Build TOF assessment
        signals["tof_assessment"] = {
            "campaigns": tof_campaigns,
            "total_orders": tof_total_orders,
            "total_revenue": tof_total_revenue,
            "avg_nc_pct": tof_avg_nc_pct,
            "meta_first_click_7d": blended.get("meta_first_click_7d", 0),
            "meta_fc_trend": blended.get("meta_fc_trend_wow", 0),
            "ncac_7d_avg": blended.get("ncac_7d_avg", 0),
            "branded_search_pct": branded_pct,
            "amazon_sales_7d": blended.get("amazon_sales_7d", 0),
            "amazon_trend": blended.get("amazon_trend_wow", 0),
            "verdict": None,
        }

        # Determine TOF verdict
        ncac = blended.get("ncac_7d_avg", 0)
        meta_fc_trend = blended.get("meta_fc_trend_wow", 0)

        if ncac > 0 and ncac < 50 and branded_pct >= 15:
            signals["tof_assessment"]["verdict"] = "healthy"
            signals["tof_assessment"]["message"] = (
                f"TOF appears healthy. NCAC ${ncac:.0f} is below $50 target. "
                f"Branded search at {branded_pct:.1f}% suggests good brand awareness."
            )
        elif ncac > 0 and ncac < 50:
            signals["tof_assessment"]["verdict"] = "working"
            signals["tof_assessment"]["message"] = (
                f"TOF is driving new customers (NCAC ${ncac:.0f}). "
                "Don't cut based on low direct ROAS."
            )
        else:
            signals["tof_assessment"]["verdict"] = "needs_review"
            signals["tof_assessment"]["message"] = (
                "TOF needs review. Check if branded search correlates with TOF spend changes."
            )

    # Sort by ROAS
    signals["campaigns_to_scale"].sort(key=lambda x: x["roas"], reverse=True)
    signals["campaigns_to_watch"].sort(key=lambda x: x["roas"])

    # Generate alerts
    platform_vs_kendall = r.get("platform_vs_kendall", {})
    over_attribution_pct = platform_vs_kendall.get("over_attribution_pct", 0)

    if over_attribution_pct > 40:
        signals["alerts"].append(
            f"Platforms over-claiming revenue by {over_attribution_pct:.0f}%. "
            "Use Kendall attribution, not platform ROAS."
        )

    # Branded search health check
    branded = r.get("branded_search", {})
    branded_pct = branded.get("branded_pct", 0)
    if branded_pct > 0 and branded_pct < 15:
        signals["alerts"].append(
            f"Branded search only {branded_pct:.1f}% of total. "
            "Consider testing TOF creative to build brand awareness."
        )
    elif branded_pct >= 20:
        signals["alerts"].append(
            f"Branded search at {branded_pct:.1f}% - strong brand awareness. "
            "TOF is likely working."
        )

    return signals
