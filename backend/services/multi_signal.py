"""
Multi-Signal Campaign Analysis Service.

Aggregates multiple data points for each campaign to enable holistic
decision-making rather than relying on any single metric.

The key insight: no single attribution source tells the whole truth.
- Platform ROAS is self-interested (over-credits itself)
- Kendall Last-Click misses awareness/assist value
- Kendall First-Click misses conversion optimization value
- Session quality shows intent but not revenue
- Cross-channel effects are invisible to single-source attribution

This service combines all signals into a unified view.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Literal
from functools import lru_cache
import statistics

# Try to import MCP client for Kendall, fall back to file-based data
try:
    from mcp import ClientSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from services.data_loader import (
    get_kendall_attribution,
    get_kendall_historical,
    get_google_ads_campaigns,
    get_meta_ads_campaigns,
    get_gsc_daily_trend,
    get_date_cutoff,
    filter_by_date,
    load_json,
    DATA_DIR,
    CACHE_TTL_HEAVY,
    cached,
    EST,
)


# Weights for the composite score (should sum to 1.0)
SIGNAL_WEIGHTS = {
    "kendall_last_click": 0.30,   # Most de-duplicated, but misses awareness
    "kendall_first_click": 0.20,  # Captures awareness/TOF value
    "platform_reported": 0.15,    # Self-interested but has view-through
    "session_quality": 0.25,      # Behavioral signal, platform-agnostic
    "trend": 0.10,                # Is performance improving or declining?
}

# Thresholds for scoring
ROAS_TARGET = 2.0        # Target ROAS for scoring
ROAS_EXCELLENT = 3.5     # Excellent ROAS threshold
BOUNCE_TARGET = 0.65     # Target max bounce rate
ATC_TARGET = 0.08        # Target add-to-cart rate
ORDER_RATE_TARGET = 0.02 # Target order rate

# Confidence thresholds based on order volume
CONFIDENCE_THRESHOLDS = {
    "high": 20,      # 20+ orders = high confidence
    "medium": 10,    # 10-19 orders = medium confidence
    "low": 3,        # 3-9 orders = low confidence
    # < 3 orders = very low confidence
}

# Budget concentration threshold for CBO campaigns
BUDGET_CONCENTRATION_THRESHOLD = 0.60  # Alert if one adset gets >60% of budget


def load_multi_timeframe_ads(platform: str) -> dict:
    """
    Load ads data for multiple timeframes (7d, 30d).

    Returns dict with '7d' and '30d' keys containing campaign data.
    Supports: facebook, google, tiktok
    """
    if platform == "facebook":
        prefix = "meta"
    elif platform == "tiktok":
        prefix = "tiktok"
    else:
        prefix = "google"

    result = {}

    for days in [7, 30]:
        filename = f"{prefix}_ads_report_{days}d.json"
        filepath = DATA_DIR / "kendall" / filename
        data = load_json(filepath)
        if data:
            result[f"{days}d"] = data

    # Fallback to single file if multi-timeframe not available
    if not result:
        filename = f"{prefix}_ads_report.json"
        filepath = DATA_DIR / "kendall" / filename
        data = load_json(filepath)
        if data:
            result["30d"] = data

    return result


def load_adset_data(platform: str, days: int = 7) -> dict:
    """
    Load adset-level data for budget concentration detection.

    Returns dict keyed by campaign_id with list of adsets.
    """
    prefix = "meta" if platform == "facebook" else "google"
    filename = f"{prefix}_adsets_{days}d.json"
    filepath = DATA_DIR / "kendall" / filename

    data = load_json(filepath)
    if not data or "adsets" not in data:
        return {}

    # Group adsets by campaign
    by_campaign = {}
    for adset_id, adset_data in data.get("adsets", {}).items():
        camp_id = adset_data.get("campaign_id", "unknown")
        if camp_id not in by_campaign:
            by_campaign[camp_id] = []
        by_campaign[camp_id].append({
            "adset_id": adset_id,
            "name": adset_data.get("name", "Unknown"),
            "spend": adset_data.get("spend", 0),
            "roas": adset_data.get("roas", 0),
            "orders": adset_data.get("orders", 0),
        })

    return by_campaign


def calculate_confidence_from_volume(orders: int) -> str:
    """
    Calculate confidence level based on conversion volume.

    More orders = more statistical confidence in ROAS.
    """
    if orders >= CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    elif orders >= CONFIDENCE_THRESHOLDS["medium"]:
        return "medium"
    elif orders >= CONFIDENCE_THRESHOLDS["low"]:
        return "low"
    else:
        return "very_low"


def calculate_trend_from_timeframes(roas_7d: float, roas_30d: float) -> dict:
    """
    Calculate trend by comparing 7d vs 30d ROAS.

    Returns:
        dict with trend direction, magnitude, and score
    """
    if roas_30d == 0:
        return {
            "direction": "unknown",
            "change_pct": 0,
            "score": 0.5,
            "interpretation": "No 30d baseline"
        }

    change_pct = ((roas_7d - roas_30d) / roas_30d) * 100

    # Determine direction
    if change_pct > 10:
        direction = "improving"
    elif change_pct < -10:
        direction = "declining"
    else:
        direction = "stable"

    # Calculate trend score (0-1)
    # Map -30% to +30% change to 0 to 1 score
    score = max(0, min(1, (change_pct + 30) / 60))

    # Interpretation
    if change_pct > 25:
        interpretation = f"Strong momentum: +{change_pct:.0f}% vs 30d avg"
    elif change_pct > 10:
        interpretation = f"Improving: +{change_pct:.0f}% vs 30d avg"
    elif change_pct < -25:
        interpretation = f"Sharp decline: {change_pct:.0f}% vs 30d avg"
    elif change_pct < -10:
        interpretation = f"Declining: {change_pct:.0f}% vs 30d avg"
    else:
        interpretation = f"Stable: {change_pct:+.0f}% vs 30d avg"

    return {
        "direction": direction,
        "change_pct": round(change_pct, 1),
        "score": round(score, 2),
        "interpretation": interpretation,
        "roas_7d": round(roas_7d, 2),
        "roas_30d": round(roas_30d, 2),
    }


def detect_budget_concentration(adsets: list, campaign_name: str) -> dict | None:
    """
    Detect if budget is concentrated in one adset (CBO concern).

    In CBO campaigns, Meta may push too much budget to one adset,
    limiting testing of other creatives/audiences.

    Returns warning dict if concentration detected, None otherwise.
    """
    if not adsets or len(adsets) < 2:
        return None

    total_spend = sum(a["spend"] for a in adsets)
    if total_spend == 0:
        return None

    # Calculate concentration
    spend_shares = [(a["name"], a["spend"] / total_spend) for a in adsets]
    spend_shares.sort(key=lambda x: x[1], reverse=True)

    top_adset_name, top_adset_share = spend_shares[0]

    if top_adset_share > BUDGET_CONCENTRATION_THRESHOLD:
        # Calculate what share "should" be for even distribution
        even_share = 1 / len(adsets)
        over_concentration = top_adset_share - even_share

        # Check if the concentrated adset is the best performer
        sorted_by_roas = sorted(adsets, key=lambda x: x.get("roas", 0), reverse=True)
        is_best_performer = sorted_by_roas[0]["name"] == top_adset_name

        return {
            "warning": True,
            "campaign_name": campaign_name,
            "top_adset": top_adset_name,
            "top_adset_share": round(top_adset_share * 100, 1),
            "adset_count": len(adsets),
            "is_best_performer": is_best_performer,
            "recommendation": (
                f"CBO concentrating {top_adset_share*100:.0f}% on '{top_adset_name}'. "
                + ("This is the best performer, so it's optimal." if is_best_performer
                   else "Consider ABO to test other adsets equally.")
            ),
            "spend_distribution": spend_shares[:3],  # Top 3
        }

    return None


def normalize_score(value: float, target: float, higher_is_better: bool = True) -> float:
    """
    Normalize a metric to a 0-1 score relative to target.

    Args:
        value: The actual metric value
        target: The target/benchmark value
        higher_is_better: True if higher values are better (e.g., ROAS, ATC rate)

    Returns:
        Score from 0 to 1, where 1 is excellent and 0 is poor
    """
    if target == 0:
        return 0.5

    ratio = value / target

    if higher_is_better:
        # Cap at 1.5x target = perfect score
        return min(1.0, ratio / 1.5)
    else:
        # For metrics where lower is better (e.g., bounce rate)
        # Invert the ratio
        return min(1.0, max(0, 2 - ratio))


def calculate_session_quality_score(
    bounce_rate: float,
    atc_rate: float,
    checkout_rate: float,
    order_rate: float
) -> float:
    """
    Calculate a composite session quality score from behavioral metrics.

    Higher score = better quality traffic
    """
    bounce_score = normalize_score(bounce_rate, BOUNCE_TARGET, higher_is_better=False)
    atc_score = normalize_score(atc_rate, ATC_TARGET, higher_is_better=True)
    order_score = normalize_score(order_rate, ORDER_RATE_TARGET, higher_is_better=True)

    # Weight the components
    return (bounce_score * 0.3 + atc_score * 0.4 + order_score * 0.3)


def calculate_trend_score(current_value: float, previous_value: float) -> float:
    """
    Calculate a trend score based on period-over-period change.

    Returns 0-1 where:
    - 1.0 = significant improvement (>20% better)
    - 0.5 = stable
    - 0.0 = significant decline (>20% worse)
    """
    if previous_value == 0:
        return 0.5  # No baseline

    pct_change = (current_value - previous_value) / previous_value

    # Map -20% to +20% change to 0 to 1 score
    normalized = (pct_change + 0.2) / 0.4
    return max(0, min(1, normalized))


def calculate_weighted_score(
    platform_roas: float,
    kendall_lc_roas: float,
    kendall_fc_roas: float,
    session_quality_score: float,
    trend_score: float
) -> tuple[float, str]:
    """
    Calculate the weighted composite score for a campaign.

    Returns:
        (score, confidence_level)
        - score: 0-1 composite score
        - confidence_level: "high", "medium", "low" based on data quality
    """
    # Normalize each ROAS to 0-1 scale
    platform_score = normalize_score(platform_roas, ROAS_TARGET)
    kendall_lc_score = normalize_score(kendall_lc_roas, ROAS_TARGET)
    kendall_fc_score = normalize_score(kendall_fc_roas, ROAS_TARGET)

    # Calculate weighted score
    weighted = (
        kendall_lc_score * SIGNAL_WEIGHTS["kendall_last_click"] +
        kendall_fc_score * SIGNAL_WEIGHTS["kendall_first_click"] +
        platform_score * SIGNAL_WEIGHTS["platform_reported"] +
        session_quality_score * SIGNAL_WEIGHTS["session_quality"] +
        trend_score * SIGNAL_WEIGHTS["trend"]
    )

    # Determine confidence based on agreement between sources
    scores = [platform_score, kendall_lc_score, kendall_fc_score]
    score_std = statistics.stdev(scores) if len(scores) >= 2 else 0

    if score_std < 0.15:
        confidence = "high"  # Sources agree
    elif score_std < 0.30:
        confidence = "medium"  # Some disagreement
    else:
        confidence = "low"  # Significant disagreement

    return (weighted, confidence)


def classify_campaign_role(
    campaign_name: str,
    kendall_fc_roas: float,
    kendall_lc_roas: float,
    nc_percent: float
) -> str:
    """
    Classify what role this campaign plays in the funnel.

    Returns: "awareness", "consideration", "conversion", "retention", "mixed"
    """
    name_lower = campaign_name.lower()

    # Check explicit naming
    if any(kw in name_lower for kw in ["tof", "prospecting", "awareness", "cold", "discovery"]):
        return "awareness"
    if any(kw in name_lower for kw in ["mof", "consideration", "engaged"]):
        return "consideration"
    if any(kw in name_lower for kw in ["bof", "retargeting", "cart", "checkout"]):
        return "conversion"
    if any(kw in name_lower for kw in ["retention", "past customer", "repeat", "loyalty"]):
        return "retention"

    # Infer from metrics
    fc_to_lc_ratio = kendall_fc_roas / kendall_lc_roas if kendall_lc_roas > 0 else 0

    if fc_to_lc_ratio > 0.9 and nc_percent > 0.7:
        return "awareness"  # First-click ~ last-click, mostly new customers
    elif fc_to_lc_ratio < 0.5 and nc_percent < 0.3:
        return "retention"  # Last-click much better, mostly returning customers
    elif nc_percent > 0.5:
        return "consideration"
    else:
        return "mixed"


def get_platform_vs_kendall_gap(platform_roas: float, kendall_roas: float) -> dict:
    """
    Calculate the gap between platform-reported and Kendall-attributed ROAS.

    A large gap indicates the platform is over-claiming credit.
    """
    if kendall_roas == 0:
        gap_pct = 100 if platform_roas > 0 else 0
    else:
        gap_pct = ((platform_roas - kendall_roas) / kendall_roas) * 100

    return {
        "gap_percent": round(gap_pct, 1),
        "platform_roas": platform_roas,
        "kendall_roas": kendall_roas,
        "trust_level": (
            "high" if gap_pct < 20 else
            "medium" if gap_pct < 50 else
            "low"
        ),
        "interpretation": (
            "Platform and Kendall agree" if gap_pct < 20 else
            "Platform slightly over-claiming" if gap_pct < 50 else
            "Platform significantly over-claiming - use Kendall" if gap_pct < 100 else
            "Platform massively over-claiming - investigate view-through attribution"
        )
    }


@cached(ttl=CACHE_TTL_HEAVY)
def get_multi_signal_campaign_view(
    platform: Literal["facebook", "google"],
    days: int = 30,
    min_spend: float = 50.0,
    level: Literal["campaign", "adset", "ad"] = "campaign"
) -> dict:
    """
    Get a comprehensive multi-signal view of all campaigns for a platform.

    This is the main function that aggregates all data points for LLM analysis.
    Uses multi-timeframe Kendall ads reports (7d, 30d) for trend detection.

    Args:
        platform: "facebook" or "google"
        days: Number of days to analyze
        min_spend: Minimum spend threshold to include
        level: Granularity level

    Returns:
        Dictionary with campaigns and their multi-signal scores
    """
    # Load multi-timeframe ads data
    multi_tf_data = load_multi_timeframe_ads(platform)

    # Use 30d data as primary, 7d for trend detection
    ads_report_30d = multi_tf_data.get("30d", {})
    ads_report_7d = multi_tf_data.get("7d", {})

    # Load adset data for budget concentration detection
    adset_data = load_adset_data(platform, days=7)

    channel_name = "Meta Ads" if platform == "facebook" else "Google Ads"
    campaigns = []
    budget_warnings = []

    # Build 7d ROAS lookup for trend calculation
    roas_7d_by_id = {}
    if ads_report_7d and "camps" in ads_report_7d:
        for camp_id, camp_data in ads_report_7d["camps"].items():
            roas_7d_by_id[camp_id] = camp_data.get("roas", 0)

    # If we have Kendall ads report, use it directly (preferred)
    if ads_report_30d and "camps" in ads_report_30d:
        for camp_id, camp_data in ads_report_30d["camps"].items():
            spend = camp_data.get("spend", 0)
            if spend < min_spend:
                continue

            name = camp_data.get("c_name", "Unknown")
            kendall_lc_roas_30d = camp_data.get("roas", 0)
            kendall_lc_roas_7d = roas_7d_by_id.get(camp_id, kendall_lc_roas_30d)
            platform_roas = camp_data.get("plat_roas", 0)

            # Estimate first-click ROAS (TOF campaigns will be higher)
            kendall_fc_roas = kendall_lc_roas_30d * 0.8  # Conservative estimate

            # Session quality from Kendall data
            bounce_rate = camp_data.get("bounce", 0.7)
            atc_rate = camp_data.get("atc_rate", 0.05)
            checkout_rate = camp_data.get("co_rate", 0.02)
            order_rate = camp_data.get("order_rate", 0.01)

            session_quality = calculate_session_quality_score(
                bounce_rate, atc_rate, checkout_rate, order_rate
            )

            # Calculate trend from multi-timeframe data (7d vs 30d)
            trend_data = calculate_trend_from_timeframes(kendall_lc_roas_7d, kendall_lc_roas_30d)
            trend_score = trend_data["score"]

            # Get order count for confidence calculation
            orders = camp_data.get("orders", 0)

            # Calculate confidence based on order volume (not just signal agreement)
            volume_confidence = calculate_confidence_from_volume(orders)

            # Calculate weighted composite score
            weighted_score, signal_confidence = calculate_weighted_score(
                platform_roas, kendall_lc_roas_30d, kendall_fc_roas,
                session_quality, trend_score
            )

            # Use the lower of volume confidence and signal confidence
            confidence_order = {"very_low": 0, "low": 1, "medium": 2, "high": 3}
            final_confidence = min(
                [volume_confidence, signal_confidence],
                key=lambda x: confidence_order.get(x, 0)
            )

            # Classify campaign role
            nc_percent = camp_data.get("attributed_newcust_percent", 0.5)
            role = classify_campaign_role(name, kendall_fc_roas, kendall_lc_roas_30d, nc_percent)

            # Platform vs Kendall gap
            attribution_gap = get_platform_vs_kendall_gap(platform_roas, kendall_lc_roas_30d)

            # Check for budget concentration in this campaign's adsets
            camp_adsets = adset_data.get(camp_id, [])
            concentration_warning = detect_budget_concentration(camp_adsets, name)
            if concentration_warning:
                budget_warnings.append(concentration_warning)

            campaigns.append({
                "campaign_id": camp_id,
                "campaign_name": name,
                "platform": platform,
                "funnel_role": role,

                # Spend & scale
                "spend": round(spend, 2),
                "daily_spend": round(spend / max(1, days), 2),
                "days_active": days,

                # Multi-signal ROAS (using 30d as primary)
                "platform_roas": round(platform_roas, 2),
                "kendall_lc_roas": round(kendall_lc_roas_30d, 2),
                "kendall_fc_roas": round(kendall_fc_roas, 2),
                "attribution_gap": attribution_gap,

                # Multi-timeframe ROAS for trend analysis
                "roas_7d": round(kendall_lc_roas_7d, 2),
                "roas_30d": round(kendall_lc_roas_30d, 2),
                "trend": trend_data,

                # Revenue & orders
                "platform_revenue": round(camp_data.get("plat_sales", 0), 2),
                "platform_orders": camp_data.get("plat_orders", 0),
                "kendall_revenue": round(camp_data.get("sales", 0), 2),
                "kendall_orders": orders,

                # Customer acquisition
                "new_customer_percent": round(nc_percent * 100, 1),
                "nc_roas": round(camp_data.get("nc_roas", 0), 2),

                # Session quality
                "sessions": camp_data.get("sessions", 0),
                "bounce_rate": round(bounce_rate * 100, 1),
                "atc_rate": round(atc_rate * 100, 1),
                "checkout_rate": round(checkout_rate * 100, 1),
                "order_rate": round(order_rate * 100, 1),
                "session_quality_score": round(session_quality, 2),

                # Composite scoring
                "weighted_score": round(weighted_score, 2),
                "confidence": final_confidence,
                "volume_confidence": volume_confidence,
                "signal_confidence": signal_confidence,
                "trend_score": round(trend_score, 2),

                # Budget concentration
                "budget_concentration_warning": concentration_warning,

                # Decision support
                "signals_summary": _generate_signals_summary(
                    platform_roas, kendall_lc_roas_30d, kendall_fc_roas,
                    session_quality, role, attribution_gap, trend_data
                ),
            })

        # Sort by weighted score descending
        campaigns.sort(key=lambda x: x["weighted_score"], reverse=True)

        return {
            "platform": platform,
            "channel_name": channel_name,
            "period_days": days,
            "min_spend_filter": min_spend,
            "campaigns": campaigns,
            "summary": _generate_platform_summary(campaigns),
            "budget_concentration_warnings": budget_warnings,
            "timeframes_available": list(multi_tf_data.keys()),
        }

    # Fallback to old method if no Kendall ads report
    attribution = get_kendall_attribution()
    historical = get_kendall_historical()

    if platform == "facebook":
        local_campaigns = get_meta_ads_campaigns()
    else:
        local_campaigns = get_google_ads_campaigns()

    channel_data = attribution.get(channel_name, {}) if attribution else {}
    breakdowns = channel_data.get("breakdowns", {})

    # Process local campaign data
    if local_campaigns:
        # Filter by date
        filtered = filter_by_date(local_campaigns, days)

        # Aggregate by campaign
        campaign_totals = {}
        for c in filtered:
            name = c.get("campaign_name", "Unknown")
            cid = c.get("campaign_id", "")

            if name not in campaign_totals:
                campaign_totals[name] = {
                    "campaign_id": cid,
                    "campaign_name": name,
                    "spend": 0,
                    "platform_revenue": 0,
                    "platform_orders": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "days_active": 0,
                }

            campaign_totals[name]["spend"] += c.get("spend", 0)
            campaign_totals[name]["impressions"] += c.get("impressions", 0)
            campaign_totals[name]["clicks"] += c.get("clicks", 0)
            campaign_totals[name]["days_active"] += 1

            if platform == "facebook":
                campaign_totals[name]["platform_revenue"] += c.get("purchase_value", 0)
                campaign_totals[name]["platform_orders"] += c.get("purchases", 0)
            else:
                campaign_totals[name]["platform_revenue"] += c.get("conversion_value", 0)
                campaign_totals[name]["platform_orders"] += c.get("conversions", 0)

        # Enrich with Kendall attribution data
        for name, camp in campaign_totals.items():
            if camp["spend"] < min_spend:
                continue

            # Get Kendall data for this campaign
            kendall_data = breakdowns.get(name, {})

            # Calculate platform ROAS
            platform_roas = camp["platform_revenue"] / camp["spend"] if camp["spend"] > 0 else 0

            # Get Kendall ROAS (last-click)
            kendall_lc_roas = kendall_data.get("roas", 0)
            kendall_lc_orders = kendall_data.get("orders", 0)
            kendall_lc_sales = kendall_data.get("sales", 0)
            nc_percent = kendall_data.get("nc_pct", 0)

            # For first-click, we'd need to call Kendall API - estimate from historical
            # This is a simplification; in production, call the API with first_click model
            kendall_fc_roas = kendall_lc_roas * 0.7  # Rough estimate, TOF will be higher

            # Session quality metrics (from Kendall attribution data or estimate)
            sessions = kendall_data.get("sessions", camp["clicks"])
            bounce_rate = kendall_data.get("bounce_rate", 0.7)
            atc_rate = kendall_data.get("atc_rate", 0.05)
            checkout_rate = kendall_data.get("checkout_rate", 0.02)
            order_rate = kendall_data.get("order_rate", 0.01)

            session_quality = calculate_session_quality_score(
                bounce_rate, atc_rate, checkout_rate, order_rate
            )

            # Trend score (compare to previous period)
            trend_score = 0.5  # Default neutral
            # TODO: Calculate actual trend from historical data

            # Calculate weighted composite score
            weighted_score, confidence = calculate_weighted_score(
                platform_roas,
                kendall_lc_roas,
                kendall_fc_roas,
                session_quality,
                trend_score
            )

            # Classify campaign role
            role = classify_campaign_role(name, kendall_fc_roas, kendall_lc_roas, nc_percent)

            # Platform vs Kendall gap
            attribution_gap = get_platform_vs_kendall_gap(platform_roas, kendall_lc_roas)

            campaigns.append({
                "campaign_id": camp["campaign_id"],
                "campaign_name": name,
                "platform": platform,
                "funnel_role": role,

                # Spend & scale
                "spend": round(camp["spend"], 2),
                "daily_spend": round(camp["spend"] / max(1, camp["days_active"]), 2),
                "days_active": camp["days_active"],

                # Multi-signal ROAS
                "platform_roas": round(platform_roas, 2),
                "kendall_lc_roas": round(kendall_lc_roas, 2),
                "kendall_fc_roas": round(kendall_fc_roas, 2),
                "attribution_gap": attribution_gap,

                # Revenue & orders
                "platform_revenue": round(camp["platform_revenue"], 2),
                "platform_orders": camp["platform_orders"],
                "kendall_revenue": round(kendall_lc_sales, 2),
                "kendall_orders": kendall_lc_orders,

                # Customer acquisition
                "new_customer_percent": round(nc_percent * 100, 1),
                "nc_roas": round(kendall_data.get("nc_roas", 0), 2),

                # Session quality
                "sessions": sessions,
                "bounce_rate": round(bounce_rate * 100, 1),
                "atc_rate": round(atc_rate * 100, 1),
                "checkout_rate": round(checkout_rate * 100, 1),
                "order_rate": round(order_rate * 100, 1),
                "session_quality_score": round(session_quality, 2),

                # Composite scoring
                "weighted_score": round(weighted_score, 2),
                "confidence": confidence,
                "trend_score": round(trend_score, 2),

                # Decision support
                "signals_summary": _generate_signals_summary(
                    platform_roas, kendall_lc_roas, kendall_fc_roas,
                    session_quality, role, attribution_gap
                ),
            })

    # Sort by weighted score descending
    campaigns.sort(key=lambda x: x["weighted_score"], reverse=True)

    return {
        "platform": platform,
        "channel_name": channel_name,
        "period_days": days,
        "min_spend_filter": min_spend,
        "campaigns": campaigns,
        "summary": _generate_platform_summary(campaigns),
    }


def _generate_signals_summary(
    platform_roas: float,
    kendall_lc_roas: float,
    kendall_fc_roas: float,
    session_quality: float,
    role: str,
    attribution_gap: dict,
    trend_data: dict = None
) -> dict:
    """Generate a human-readable summary of the signals for this campaign."""
    signals = []
    concerns = []
    strengths = []

    # ROAS signals
    if kendall_lc_roas >= ROAS_EXCELLENT:
        strengths.append(f"Strong last-click ROAS ({kendall_lc_roas:.1f}x)")
    elif kendall_lc_roas >= ROAS_TARGET:
        strengths.append(f"Good last-click ROAS ({kendall_lc_roas:.1f}x)")
    elif kendall_lc_roas > 0:
        concerns.append(f"Low last-click ROAS ({kendall_lc_roas:.1f}x)")

    # First-click for awareness campaigns
    if role == "awareness":
        if kendall_fc_roas >= 1.0:
            strengths.append(f"Good awareness value (FC ROAS {kendall_fc_roas:.1f}x)")
        else:
            signals.append(f"Awareness campaign - measure by NCAC, not direct ROAS")

    # Trend signals (7d vs 30d)
    if trend_data:
        direction = trend_data.get("direction", "unknown")
        change_pct = trend_data.get("change_pct", 0)

        if direction == "improving" and change_pct > 20:
            strengths.append(f"Strong momentum (+{change_pct:.0f}% 7d vs 30d)")
        elif direction == "improving":
            strengths.append(f"Improving trend (+{change_pct:.0f}% 7d vs 30d)")
        elif direction == "declining" and change_pct < -20:
            concerns.append(f"Sharp decline ({change_pct:.0f}% 7d vs 30d)")
        elif direction == "declining":
            concerns.append(f"Declining trend ({change_pct:.0f}% 7d vs 30d)")
        else:
            signals.append("Stable performance (7d ≈ 30d avg)")

    # Attribution gap
    if attribution_gap["gap_percent"] > 50:
        concerns.append(f"Platform over-claiming by {attribution_gap['gap_percent']:.0f}%")

    # Session quality
    if session_quality >= 0.7:
        strengths.append("High-quality traffic")
    elif session_quality < 0.4:
        concerns.append("Poor traffic quality (high bounce, low engagement)")

    return {
        "strengths": strengths,
        "concerns": concerns,
        "signals": signals,
        "recommendation": _infer_recommendation(
            kendall_lc_roas, role, session_quality, attribution_gap, trend_data
        )
    }


def _infer_recommendation(
    kendall_lc_roas: float,
    role: str,
    session_quality: float,
    attribution_gap: dict,
    trend_data: dict = None
) -> str:
    """Infer a preliminary recommendation based on signals including trend."""
    trend_direction = trend_data.get("direction", "stable") if trend_data else "stable"
    trend_pct = trend_data.get("change_pct", 0) if trend_data else 0

    # Awareness campaigns have different rules
    if role == "awareness":
        if session_quality >= 0.5:
            if trend_direction == "declining" and trend_pct < -20:
                return "Review creative - awareness campaign with declining performance"
            return "Maintain - awareness campaign with decent traffic quality"
        else:
            return "Review creative - awareness campaign with poor traffic quality"

    # Factor in trend for standard recommendations
    # Strong performers with positive momentum
    if kendall_lc_roas >= 3.0 and session_quality >= 0.5:
        if trend_direction == "improving":
            return "Scale aggressively - strong performer with positive momentum"
        elif trend_direction == "declining":
            return "Maintain - strong performer but declining trend, watch closely"
        return "Scale - strong performer across signals"

    elif kendall_lc_roas >= 2.0:
        if trend_direction == "improving" and trend_pct > 15:
            return "Consider scaling - meeting targets with improving trend"
        elif trend_direction == "declining" and trend_pct < -15:
            return "Watch closely - meeting targets but declining trend"
        return "Maintain - meeting targets"

    elif kendall_lc_roas >= 1.0:
        if trend_direction == "improving" and trend_pct > 20:
            return "Maintain - below target but strong improvement trend"
        elif trend_direction == "declining":
            return "Review - below target and declining, consider reducing budget"
        return "Watch - below target, monitor for improvement"

    elif kendall_lc_roas > 0:
        if trend_direction == "improving" and trend_pct > 30:
            return "Watch - underperforming but strong recovery trend"
        return "Review - underperforming, consider reducing budget"
    else:
        return "Cut - no attributed revenue"


def _generate_platform_summary(campaigns: list) -> dict:
    """Generate summary statistics for all campaigns on a platform."""
    if not campaigns:
        return {}

    total_spend = sum(c["spend"] for c in campaigns)
    total_kendall_revenue = sum(c["kendall_revenue"] for c in campaigns)
    total_platform_revenue = sum(c["platform_revenue"] for c in campaigns)

    # Count by role
    role_counts = {}
    for c in campaigns:
        role = c["funnel_role"]
        if role not in role_counts:
            role_counts[role] = {"count": 0, "spend": 0, "revenue": 0}
        role_counts[role]["count"] += 1
        role_counts[role]["spend"] += c["spend"]
        role_counts[role]["revenue"] += c["kendall_revenue"]

    # Identify top performers and underperformers
    top_performers = [c for c in campaigns if c["weighted_score"] >= 0.6][:5]
    underperformers = [c for c in campaigns if c["weighted_score"] < 0.3 and c["spend"] >= 100]

    # Calculate overall attribution gap
    overall_gap = 0
    if total_kendall_revenue > 0:
        overall_gap = ((total_platform_revenue - total_kendall_revenue) / total_kendall_revenue) * 100

    return {
        "total_campaigns": len(campaigns),
        "total_spend": round(total_spend, 2),
        "total_kendall_revenue": round(total_kendall_revenue, 2),
        "total_platform_revenue": round(total_platform_revenue, 2),
        "blended_kendall_roas": round(total_kendall_revenue / total_spend, 2) if total_spend > 0 else 0,
        "blended_platform_roas": round(total_platform_revenue / total_spend, 2) if total_spend > 0 else 0,
        "overall_attribution_gap_pct": round(overall_gap, 1),
        "by_funnel_role": role_counts,
        "top_performers_count": len(top_performers),
        "underperformers_count": len(underperformers),
        "average_weighted_score": round(
            sum(c["weighted_score"] for c in campaigns) / len(campaigns), 2
        ) if campaigns else 0,
    }


@cached(ttl=CACHE_TTL_HEAVY)
def get_cross_channel_correlation(days: int = 30) -> dict:
    """
    Calculate correlation between Meta TOF spend and Google Branded Search performance.

    This answers: "Is Meta creating demand that Google harvests?"

    Uses daily data to calculate lagged correlations.
    """
    historical = get_kendall_historical()
    gsc_trend = get_gsc_daily_trend()

    if not historical:
        return {"error": "No historical data available"}

    metrics_list = historical.get("metrics", [])
    filtered = filter_by_date(metrics_list, days)

    if len(filtered) < 14:
        return {"error": f"Need at least 14 days of data, have {len(filtered)}"}

    # Extract daily Meta spend and first-click revenue
    daily_data = []
    for m in filtered:
        daily_data.append({
            "date": m.get("date", ""),
            "meta_spend": m.get("facebook_spend", 0),
            "meta_first_click": m.get("facebook_fc", 0),
            "google_spend": m.get("google_spend", 0),
            "google_fc": m.get("google_fc", 0),
            "total_revenue": m.get("sales", 0),
            "nc_orders": m.get("nc_orders", 0),
        })

    daily_data.sort(key=lambda x: x["date"])

    # Add branded search data if available
    if gsc_trend:
        gsc_by_date = {d.get("date"): d for d in gsc_trend}
        for d in daily_data:
            gsc_data = gsc_by_date.get(d["date"], {})
            d["branded_clicks"] = gsc_data.get("branded_clicks", 0)
            d["branded_impressions"] = gsc_data.get("branded_impressions", 0)

    # Calculate correlations with different lag windows
    correlations = {}

    for lag in [0, 3, 7, 14]:
        if lag >= len(daily_data):
            continue

        # Meta spend vs. Branded search (lagged)
        meta_spend = [d["meta_spend"] for d in daily_data[:-lag] if lag > 0] if lag > 0 else [d["meta_spend"] for d in daily_data]
        branded = [d.get("branded_clicks", 0) for d in daily_data[lag:]] if lag > 0 else [d.get("branded_clicks", 0) for d in daily_data]

        if len(meta_spend) >= 7 and len(branded) >= 7:
            corr = _pearson_correlation(meta_spend[:len(branded)], branded[:len(meta_spend)])
            correlations[f"meta_spend_to_branded_lag_{lag}d"] = round(corr, 3)

        # Meta spend vs. Google first-click revenue (lagged)
        google_fc = [d["google_fc"] for d in daily_data[lag:]] if lag > 0 else [d["google_fc"] for d in daily_data]

        if len(meta_spend) >= 7 and len(google_fc) >= 7:
            corr = _pearson_correlation(meta_spend[:len(google_fc)], google_fc[:len(meta_spend)])
            correlations[f"meta_spend_to_google_fc_lag_{lag}d"] = round(corr, 3)

    # Find optimal lag (highest correlation)
    best_branded_lag = 0
    best_branded_corr = 0
    best_google_lag = 0
    best_google_corr = 0

    for key, corr in correlations.items():
        if "branded" in key and corr > best_branded_corr:
            best_branded_corr = corr
            best_branded_lag = int(key.split("_")[-1].replace("d", ""))
        if "google_fc" in key and corr > best_google_corr:
            best_google_corr = corr
            best_google_lag = int(key.split("_")[-1].replace("d", ""))

    # Interpret the correlations
    interpretation = []
    if best_branded_corr > 0.6:
        interpretation.append(
            f"Strong correlation ({best_branded_corr:.2f}) between Meta spend and branded search "
            f"with {best_branded_lag}-day lag. Meta is likely driving brand awareness."
        )
    elif best_branded_corr > 0.3:
        interpretation.append(
            f"Moderate correlation ({best_branded_corr:.2f}) between Meta spend and branded search."
        )

    if best_google_corr > 0.6:
        interpretation.append(
            f"Strong correlation ({best_google_corr:.2f}) between Meta spend and Google first-click "
            f"revenue with {best_google_lag}-day lag. Meta may be creating demand that Google captures."
        )

    # Calculate week-over-week trends
    if len(daily_data) >= 14:
        current_week = daily_data[-7:]
        previous_week = daily_data[-14:-7]

        current_meta = sum(d["meta_spend"] for d in current_week)
        previous_meta = sum(d["meta_spend"] for d in previous_week)
        meta_trend = ((current_meta - previous_meta) / previous_meta * 100) if previous_meta > 0 else 0

        current_branded = sum(d.get("branded_clicks", 0) for d in current_week)
        previous_branded = sum(d.get("branded_clicks", 0) for d in previous_week)
        branded_trend = ((current_branded - previous_branded) / previous_branded * 100) if previous_branded > 0 else 0

        current_google_fc = sum(d["google_fc"] for d in current_week)
        previous_google_fc = sum(d["google_fc"] for d in previous_week)
        google_trend = ((current_google_fc - previous_google_fc) / previous_google_fc * 100) if previous_google_fc > 0 else 0

        # Check if trends move together
        if meta_trend < -10 and branded_trend < -10:
            interpretation.append(
                f"Warning: Meta spend down {meta_trend:.0f}% and branded search down {branded_trend:.0f}%. "
                "Cutting Meta TOF may be hurting brand awareness."
            )
        elif meta_trend > 10 and branded_trend > 10:
            interpretation.append(
                f"Meta spend up {meta_trend:.0f}% and branded search up {branded_trend:.0f}%. "
                "Investment in Meta appears to be building brand."
            )

    return {
        "period_days": days,
        "data_points": len(daily_data),
        "correlations": correlations,
        "best_meta_to_branded": {
            "correlation": best_branded_corr,
            "optimal_lag_days": best_branded_lag,
            "strength": (
                "strong" if best_branded_corr > 0.6 else
                "moderate" if best_branded_corr > 0.3 else
                "weak"
            )
        },
        "best_meta_to_google_fc": {
            "correlation": best_google_corr,
            "optimal_lag_days": best_google_lag,
            "strength": (
                "strong" if best_google_corr > 0.6 else
                "moderate" if best_google_corr > 0.3 else
                "weak"
            )
        },
        "interpretation": interpretation,
        "implication": _get_correlation_implication(best_branded_corr, best_google_corr),
        "daily_data": daily_data,
    }


def _pearson_correlation(x: list, y: list) -> float:
    """Calculate Pearson correlation coefficient."""
    n = min(len(x), len(y))
    if n < 3:
        return 0

    x = x[:n]
    y = y[:n]

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(a * b for a, b in zip(x, y))
    sum_x2 = sum(a * a for a in x)
    sum_y2 = sum(b * b for b in y)

    numerator = n * sum_xy - sum_x * sum_y
    denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

    return numerator / denominator if denominator > 0 else 0


def _get_correlation_implication(branded_corr: float, google_fc_corr: float) -> str:
    """Get strategic implication of the cross-channel correlations."""
    if branded_corr > 0.5 or google_fc_corr > 0.5:
        return (
            "Meta TOF spend appears to drive downstream conversions through Google. "
            "Be cautious about cutting Meta TOF based solely on direct ROAS - "
            "it may be feeding your Google branded/shopping performance."
        )
    elif branded_corr > 0.3 or google_fc_corr > 0.3:
        return (
            "There is moderate correlation between Meta spend and Google performance. "
            "Consider running a holdout test to validate causation before major budget shifts."
        )
    else:
        return (
            "Weak correlation between Meta and Google channels. "
            "They may be operating more independently - optimize each on its own merits."
        )


def get_campaign_for_llm_context(
    platform: Literal["facebook", "google"],
    days: int = 30
) -> str:
    """
    Get a text summary of campaign performance suitable for LLM context.

    This formats the multi-signal data in a way the LLM can reason about.
    Includes trend data (7d vs 30d) and confidence levels.
    """
    data = get_multi_signal_campaign_view(platform, days)

    lines = [
        f"## {data['channel_name']} Campaign Analysis ({days} days)",
        "",
        f"**Summary:**",
        f"- Total campaigns: {data['summary'].get('total_campaigns', 0)}",
        f"- Total spend: ${data['summary'].get('total_spend', 0):,.2f}",
        f"- Blended Kendall ROAS: {data['summary'].get('blended_kendall_roas', 0):.2f}x",
        f"- Platform over-attribution: {data['summary'].get('overall_attribution_gap_pct', 0):.0f}%",
        "",
        "**Campaigns by performance (weighted score):**",
        "",
    ]

    for camp in data["campaigns"][:15]:
        signals = camp["signals_summary"]
        strengths_str = ", ".join(signals["strengths"][:3]) if signals["strengths"] else "None"
        concerns_str = ", ".join(signals["concerns"][:3]) if signals["concerns"] else "None"

        # Get trend data
        trend = camp.get("trend", {})
        trend_str = trend.get("interpretation", "No trend data")

        # Get confidence info
        vol_conf = camp.get("volume_confidence", camp.get("confidence", "unknown"))
        orders = camp.get("kendall_orders", 0)

        lines.append(f"### {camp['campaign_name']}")
        lines.append(f"- Role: {camp['funnel_role']}")
        lines.append(f"- Spend: ${camp['spend']:,.2f} (${camp['daily_spend']:.2f}/day)")
        lines.append(f"- **ROAS**: Platform {camp['platform_roas']:.2f}x | Kendall LC {camp['kendall_lc_roas']:.2f}x")
        lines.append(f"- **Trend (7d vs 30d)**: {trend_str}")
        lines.append(f"- **Confidence**: {camp['confidence']} ({orders} orders - {vol_conf} volume confidence)")
        lines.append(f"- Weighted Score: {camp['weighted_score']:.2f}")
        lines.append(f"- Session Quality: {camp['session_quality_score']:.2f} (bounce {camp['bounce_rate']:.0f}%, ATC {camp['atc_rate']:.1f}%)")

        # Add budget concentration warning if present
        concentration = camp.get("budget_concentration_warning")
        if concentration:
            lines.append(f"- **⚠️ Budget Concentration**: {concentration['recommendation']}")

        lines.append(f"- Strengths: {strengths_str}")
        lines.append(f"- Concerns: {concerns_str}")
        lines.append(f"- Initial assessment: {signals['recommendation']}")
        lines.append("")

    return "\n".join(lines)
