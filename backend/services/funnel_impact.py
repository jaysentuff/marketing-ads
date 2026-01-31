"""
Funnel Impact Detector Service.

Tracks marketing changes and measures their downstream effects across the full funnel:
- Branded search changes
- Email signups (Klaviyo)
- Retargeting conversions
- Total revenue

The key insight: a TOF campaign with low direct ROAS may be driving branded search,
which then converts via retargeting or email. We need to track the FULL impact,
not just single-platform attribution.

Timeframe strategy:
- 3d & 7d = ACTION windows (make scaling decisions)
- 14d & 30d = VALIDATION windows (confirm overall strategy is working)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from services.changelog import load_changelog, get_recent_entries
from services.data_loader import (
    get_kendall_historical,
    get_gsc_daily_trend,
    get_klaviyo_summary,
    get_date_cutoff,
    cached,
    CACHE_TTL_HEAVY,
)

EST = ZoneInfo("America/New_York")

# Store impact tracking data
DATA_DIR = Path(__file__).parent.parent.parent / "connectors" / "data"
IMPACT_FILE = DATA_DIR / "funnel_impact_tracking.json"

# Timeframes to track (in days)
TRACKING_WINDOWS = [3, 7, 14, 30]

# Minimum spend threshold for reliable impact measurement
MIN_SPEND_THRESHOLD = 100.0  # $100 minimum spend change to track

# Cooling off period - don't recommend changes to items changed recently
COOLING_OFF_DAYS = 3


def _load_impact_data() -> dict:
    """Load impact tracking data from file."""
    try:
        with open(IMPACT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tracked_changes": [], "last_updated": None}


def _save_impact_data(data: dict) -> None:
    """Save impact tracking data to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now(EST).isoformat()
    with open(IMPACT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def get_funnel_metrics_for_period(start_date: str, end_date: str) -> dict:
    """
    Get aggregated funnel metrics for a specific date range.

    Returns metrics from multiple signals:
    - Shopify revenue & orders (final conversion)
    - New customers (growth signal)
    - Branded search clicks (awareness signal)
    - Meta first-click attribution (TOF credit)
    - Amazon sales (halo effect)
    """
    historical = get_kendall_historical()
    if not historical:
        return {}

    metrics_list = historical.get("metrics", [])

    # Filter to date range
    filtered = [
        m for m in metrics_list
        if start_date <= m.get("date", "") <= end_date
    ]

    if not filtered:
        return {}

    # Aggregate metrics
    total_revenue = sum(m.get("sales", 0) for m in filtered)
    total_orders = sum(m.get("orders", 0) for m in filtered)
    total_nc_orders = sum(m.get("nc_orders", 0) for m in filtered)
    total_spend = sum(m.get("spend", 0) for m in filtered)
    total_meta_spend = sum(m.get("facebook_spend", 0) for m in filtered)
    total_google_spend = sum(m.get("google_spend", 0) for m in filtered)
    total_amazon_sales = sum(m.get("amz_us_sales", 0) for m in filtered)
    total_meta_fc = sum(m.get("facebook_fc", 0) for m in filtered)
    total_cam = sum(m.get("contrib_after_mkt", 0) for m in filtered)

    # Average efficiency metrics
    avg_mer = sum(m.get("mer", 0) for m in filtered) / len(filtered) if filtered else 0
    avg_ncac = sum(m.get("ncac", 0) for m in filtered) / len(filtered) if filtered else 0

    # Get branded search data
    branded_clicks = 0
    gsc_data = get_gsc_daily_trend()
    if gsc_data:
        branded_clicks = sum(
            d.get("branded_clicks", 0) for d in gsc_data
            if start_date <= d.get("date", "") <= end_date
        )

    return {
        "revenue": round(total_revenue, 2),
        "orders": total_orders,
        "new_customers": total_nc_orders,
        "ad_spend": round(total_spend, 2),
        "meta_spend": round(total_meta_spend, 2),
        "google_spend": round(total_google_spend, 2),
        "amazon_sales": round(total_amazon_sales, 2),
        "meta_first_click": round(total_meta_fc, 2),
        "cam": round(total_cam, 2),
        "branded_clicks": branded_clicks,
        "mer": round(avg_mer, 2),
        "ncac": round(avg_ncac, 2),
        "days": len(filtered),
    }


def calculate_impact(baseline: dict, after: dict) -> dict:
    """
    Calculate the impact of a change by comparing baseline to after metrics.

    Returns absolute and percentage changes for each metric.
    """
    if not baseline or not after:
        return {"error": "Missing data for comparison"}

    def calc_change(after_val: float, baseline_val: float) -> dict:
        absolute = after_val - baseline_val
        pct = ((after_val - baseline_val) / baseline_val * 100) if baseline_val > 0 else (100 if after_val > 0 else 0)
        direction = "up" if pct > 2 else "down" if pct < -2 else "flat"
        return {
            "baseline": baseline_val,
            "after": after_val,
            "absolute": round(absolute, 2),
            "pct": round(pct, 1),
            "direction": direction,
        }

    return {
        "revenue": calc_change(after.get("revenue", 0), baseline.get("revenue", 0)),
        "orders": calc_change(after.get("orders", 0), baseline.get("orders", 0)),
        "new_customers": calc_change(after.get("new_customers", 0), baseline.get("new_customers", 0)),
        "amazon_sales": calc_change(after.get("amazon_sales", 0), baseline.get("amazon_sales", 0)),
        "branded_clicks": calc_change(after.get("branded_clicks", 0), baseline.get("branded_clicks", 0)),
        "meta_first_click": calc_change(after.get("meta_first_click", 0), baseline.get("meta_first_click", 0)),
        "mer": calc_change(after.get("mer", 0), baseline.get("mer", 0)),
        "ncac": calc_change(after.get("ncac", 0), baseline.get("ncac", 0)),
    }


def assess_funnel_impact(impact: dict) -> dict:
    """
    Assess the overall funnel impact from individual metric changes.

    Signal weights (tuned for TuffWraps growth mode):
    - Revenue: 2.5x (final outcome, but not so dominant it ignores leading indicators)
    - New Customers: 2.5x (growth mode - NC = future revenue)
    - Amazon: 2x (25-30% of total revenue - significant channel)
    - Branded Search: 1.5x (awareness indicator - let data prove if predictive)
    - MER: 1x (efficiency sanity check)

    These weights can be adjusted based on business priorities.
    """
    if "error" in impact:
        return {"verdict": "unknown", "reason": impact["error"]}

    # Score each signal (positive = good)
    scores = []
    signals = []

    # Revenue (weight: 2.5) - final outcome but balanced
    revenue = impact.get("revenue", {})
    if revenue.get("direction") == "up":
        scores.append(2.5)
        signals.append(f"Revenue up {revenue.get('pct', 0):.1f}%")
    elif revenue.get("direction") == "down":
        scores.append(-2.5)
        signals.append(f"Revenue down {abs(revenue.get('pct', 0)):.1f}%")
    else:
        signals.append("Revenue flat")

    # New customers (weight: 2.5) - growth signal, equal to revenue in growth mode
    nc = impact.get("new_customers", {})
    if nc.get("direction") == "up":
        scores.append(2.5)
        signals.append(f"New customers up {nc.get('pct', 0):.1f}%")
    elif nc.get("direction") == "down":
        scores.append(-2.5)
        signals.append(f"New customers down {abs(nc.get('pct', 0)):.1f}%")

    # Amazon sales (weight: 2) - 25-30% of revenue, significant halo effect
    amazon = impact.get("amazon_sales", {})
    if amazon.get("direction") == "up":
        scores.append(2)
        signals.append(f"Amazon up {amazon.get('pct', 0):.1f}%")
    elif amazon.get("direction") == "down":
        scores.append(-2)
        signals.append(f"Amazon down {abs(amazon.get('pct', 0)):.1f}%")

    # Branded search (weight: 1.5) - awareness signal, let data prove if predictive
    branded = impact.get("branded_clicks", {})
    if branded.get("direction") == "up":
        scores.append(1.5)
        signals.append(f"Branded search up {branded.get('pct', 0):.1f}%")
    elif branded.get("direction") == "down":
        scores.append(-1.5)
        signals.append(f"Branded search down {abs(branded.get('pct', 0)):.1f}%")

    # MER (efficiency - weight: 1)
    mer = impact.get("mer", {})
    if mer.get("direction") == "up":
        scores.append(1)
        signals.append(f"MER improved {mer.get('pct', 0):.1f}%")
    elif mer.get("direction") == "down":
        scores.append(-1)
        signals.append(f"MER declined {abs(mer.get('pct', 0)):.1f}%")

    # Calculate total score
    total_score = sum(scores)

    # Determine verdict
    if total_score >= 4:
        verdict = "strong_positive"
        reason = "Multiple signals confirm positive impact"
    elif total_score >= 2:
        verdict = "positive"
        reason = "Overall positive funnel impact"
    elif total_score >= 0:
        verdict = "neutral"
        reason = "Mixed or flat signals"
    elif total_score >= -2:
        verdict = "slightly_negative"
        reason = "Some negative signals, monitor closely"
    else:
        verdict = "negative"
        reason = "Multiple signals show negative impact"

    return {
        "verdict": verdict,
        "score": round(total_score, 1),
        "reason": reason,
        "signals": signals,
    }


def get_change_impact_status(change_entry: dict, now: Optional[datetime] = None) -> dict:
    """
    Get the current impact status for a changelog entry.

    For each tracking window (3d, 7d, 14d, 30d), calculates:
    - Whether enough time has passed
    - What the baseline metrics were
    - What the after metrics are
    - The calculated impact
    """
    if now is None:
        now = datetime.now(EST)

    # Parse change date
    change_date_str = change_entry.get("timestamp", "")[:10]
    try:
        change_date = datetime.strptime(change_date_str, "%Y-%m-%d").replace(tzinfo=EST)
    except ValueError:
        return {"error": "Invalid change date"}

    days_since_change = (now - change_date).days

    # Get baseline period (same number of days before the change)
    # We'll use 7 days before the change as baseline for all windows
    baseline_start = (change_date - timedelta(days=7)).strftime("%Y-%m-%d")
    baseline_end = (change_date - timedelta(days=1)).strftime("%Y-%m-%d")
    baseline_metrics = get_funnel_metrics_for_period(baseline_start, baseline_end)

    # Calculate impact for each window
    windows = {}
    for window_days in TRACKING_WINDOWS:
        if days_since_change >= window_days:
            # We have enough data for this window
            after_start = change_date_str
            after_end = (change_date + timedelta(days=window_days - 1)).strftime("%Y-%m-%d")
            after_metrics = get_funnel_metrics_for_period(after_start, after_end)

            impact = calculate_impact(baseline_metrics, after_metrics)
            assessment = assess_funnel_impact(impact)

            windows[f"{window_days}d"] = {
                "status": "complete",
                "days_since_change": days_since_change,
                "baseline_period": f"{baseline_start} to {baseline_end}",
                "after_period": f"{after_start} to {after_end}",
                "impact": impact,
                "assessment": assessment,
            }
        else:
            # Not enough time yet
            days_remaining = window_days - days_since_change
            windows[f"{window_days}d"] = {
                "status": "pending",
                "days_since_change": days_since_change,
                "days_remaining": days_remaining,
                "available_on": (change_date + timedelta(days=window_days)).strftime("%Y-%m-%d"),
            }

    return {
        "change_id": change_entry.get("id"),
        "change_date": change_date_str,
        "channel": change_entry.get("channel"),
        "campaign": change_entry.get("campaign"),
        "description": change_entry.get("description"),
        "action_type": change_entry.get("action_type"),
        "days_since_change": days_since_change,
        "baseline_metrics": baseline_metrics,
        "windows": windows,
    }


@cached(ttl=CACHE_TTL_HEAVY)
def get_all_change_impacts(days: int = 30) -> list[dict]:
    """
    Get impact status for all recent changelog entries.

    Returns a list of changes with their multi-timeframe impact assessments.
    """
    entries = get_recent_entries(days=days, limit=50)

    if not entries:
        return []

    impacts = []
    for entry in entries:
        impact = get_change_impact_status(entry)
        if "error" not in impact:
            impacts.append(impact)

    # Sort by change date descending (most recent first)
    impacts.sort(key=lambda x: x.get("change_date", ""), reverse=True)

    return impacts


def get_items_in_cooling_off(days: int = COOLING_OFF_DAYS) -> dict:
    """
    Get channels and campaigns that are in the cooling off period.

    These should not receive new recommendations until the cooling off period expires.
    """
    entries = get_recent_entries(days=days, limit=100)

    cooling_off = {
        "channels": set(),
        "campaigns": set(),
        "entries": [],
    }

    for entry in entries:
        channel = entry.get("channel", "")
        campaign = entry.get("campaign", "")
        change_date = entry.get("timestamp", "")[:10]

        if channel:
            # Normalize channel names
            if "meta" in channel.lower():
                cooling_off["channels"].add("Meta")
            if "google" in channel.lower():
                cooling_off["channels"].add("Google")

        if campaign:
            cooling_off["campaigns"].add(campaign)

        cooling_off["entries"].append({
            "id": entry.get("id"),
            "date": change_date,
            "channel": channel,
            "campaign": campaign,
            "description": entry.get("description"),
        })

    # Convert sets to lists for JSON serialization
    cooling_off["channels"] = list(cooling_off["channels"])
    cooling_off["campaigns"] = list(cooling_off["campaigns"])

    return cooling_off


def get_changes_needing_followup(analysis_type: str = "full") -> dict:
    """
    Get changes that need follow-up based on the analysis type.

    For Monday full analysis:
    - All changes with 7d window complete (primary action window)
    - All changes with 14d or 30d window newly complete (validation)

    For Thursday quick check:
    - Changes with 3d window complete (quick assessment)
    """
    all_impacts = get_all_change_impacts(days=30)

    needs_followup = {
        "action_ready": [],      # 3d/7d complete - ready for scaling decisions
        "validation_ready": [],  # 14d/30d complete - strategy validation
        "pending": [],           # Still waiting for data
    }

    for impact in all_impacts:
        windows = impact.get("windows", {})

        # Check 3d window (quick action)
        if windows.get("3d", {}).get("status") == "complete":
            assessment_3d = windows["3d"].get("assessment", {})
            if analysis_type == "quick" or analysis_type == "full":
                needs_followup["action_ready"].append({
                    "change": impact,
                    "window": "3d",
                    "verdict": assessment_3d.get("verdict"),
                    "signals": assessment_3d.get("signals", []),
                })

        # Check 7d window (primary action window)
        if windows.get("7d", {}).get("status") == "complete":
            assessment_7d = windows["7d"].get("assessment", {})
            if analysis_type == "full":
                needs_followup["action_ready"].append({
                    "change": impact,
                    "window": "7d",
                    "verdict": assessment_7d.get("verdict"),
                    "signals": assessment_7d.get("signals", []),
                })

        # Check 14d/30d windows (validation)
        for window in ["14d", "30d"]:
            if windows.get(window, {}).get("status") == "complete":
                assessment = windows[window].get("assessment", {})
                if analysis_type == "full":
                    needs_followup["validation_ready"].append({
                        "change": impact,
                        "window": window,
                        "verdict": assessment.get("verdict"),
                        "signals": assessment.get("signals", []),
                    })

        # Check for pending windows
        pending_windows = [
            w for w, data in windows.items()
            if data.get("status") == "pending"
        ]
        if pending_windows:
            needs_followup["pending"].append({
                "change": impact,
                "pending_windows": pending_windows,
                "next_available": min(
                    windows[w].get("available_on", "9999-99-99")
                    for w in pending_windows
                ),
            })

    return needs_followup


def build_followup_summary_for_llm(analysis_type: str = "full") -> str:
    """
    Build a text summary of changes needing follow-up for the LLM prompt.

    This gets included in the AI synthesis context so Claude knows what
    past changes need status updates.
    """
    followups = get_changes_needing_followup(analysis_type)
    cooling_off = get_items_in_cooling_off()

    lines = []

    # Cooling off period items
    if cooling_off["channels"] or cooling_off["campaigns"]:
        lines.append("## Items in Cooling Off Period (changed <3 days ago - don't recommend changes)")
        for entry in cooling_off["entries"][:5]:
            lines.append(f"- {entry['date']}: {entry['description']} ({entry['channel']})")
        lines.append("")

    # Action-ready changes (3d/7d)
    action_ready = followups.get("action_ready", [])
    if action_ready:
        lines.append("## Changes Ready for Action Assessment (3-7 day data)")
        lines.append("*Use these to make scaling decisions - increase, decrease, or hold*")
        lines.append("")

        for item in action_ready:
            change = item["change"]
            window = item["window"]
            verdict = item["verdict"]
            signals = item["signals"]

            lines.append(f"### {change['description']} ({change['channel']})")
            lines.append(f"- Changed: {change['change_date']} ({change['days_since_change']} days ago)")
            lines.append(f"- {window} Assessment: **{verdict.upper().replace('_', ' ')}**")
            lines.append(f"- Signals: {', '.join(signals)}")

            # Include key metrics
            impact = change["windows"][window].get("impact", {})
            revenue = impact.get("revenue", {})
            nc = impact.get("new_customers", {})
            branded = impact.get("branded_clicks", {})

            lines.append(f"- Revenue: {revenue.get('direction', 'N/A')} ({revenue.get('pct', 0):+.1f}%)")
            lines.append(f"- New Customers: {nc.get('direction', 'N/A')} ({nc.get('pct', 0):+.1f}%)")
            lines.append(f"- Branded Search: {branded.get('direction', 'N/A')} ({branded.get('pct', 0):+.1f}%)")
            lines.append("")

    # Validation-ready changes (14d/30d)
    validation_ready = followups.get("validation_ready", [])
    if validation_ready:
        lines.append("## Changes Ready for Validation (14-30 day data)")
        lines.append("*Use these to confirm overall strategy is working*")
        lines.append("")

        for item in validation_ready:
            change = item["change"]
            window = item["window"]
            verdict = item["verdict"]
            signals = item["signals"]

            lines.append(f"### {change['description']} ({change['channel']})")
            lines.append(f"- Changed: {change['change_date']}")
            lines.append(f"- {window} Validation: **{verdict.upper().replace('_', ' ')}**")
            lines.append(f"- Signals: {', '.join(signals)}")
            lines.append("")

    # Pending changes
    pending = followups.get("pending", [])
    if pending:
        lines.append("## Changes Still Pending Data")
        for item in pending[:5]:  # Limit to 5
            change = item["change"]
            pending_windows = item["pending_windows"]
            next_available = item["next_available"]

            lines.append(f"- {change['description']} ({change['channel']}): waiting for {', '.join(pending_windows)} - next data on {next_available}")
        lines.append("")

    if not lines:
        return "No recent changes to follow up on."

    return "\n".join(lines)


def get_funnel_health_snapshot() -> dict:
    """
    Get a current snapshot of funnel health for the LLM context.

    This shows the overall funnel performance to help contextualize
    individual change impacts.
    """
    # Get last 7 days as "current"
    now = datetime.now(EST)
    current_end = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    current_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    current = get_funnel_metrics_for_period(current_start, current_end)

    # Get previous 7 days as comparison
    prev_end = (now - timedelta(days=8)).strftime("%Y-%m-%d")
    prev_start = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    previous = get_funnel_metrics_for_period(prev_start, prev_end)

    # Calculate week-over-week changes
    impact = calculate_impact(previous, current)
    assessment = assess_funnel_impact(impact)

    return {
        "period": f"{current_start} to {current_end}",
        "current_metrics": current,
        "wow_impact": impact,
        "health_assessment": assessment,
    }


# =============================================================================
# CORRELATION LEARNING - Validate Signal Weights Over Time
# =============================================================================

CORRELATION_FILE = DATA_DIR / "signal_correlations.json"

# Lag periods to analyze (in days)
LAG_PERIODS = [0, 3, 7, 14]  # Same week, 3 days later, 1 week later, 2 weeks later


def _load_correlation_data() -> dict:
    """Load correlation learning data from file."""
    try:
        with open(CORRELATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "observations": [],
            "correlations": {},
            "last_updated": None,
            "weight_suggestions": {},
        }


def _save_correlation_data(data: dict) -> None:
    """Save correlation learning data to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now(EST).isoformat()
    with open(CORRELATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def calculate_signal_correlation(
    leading_signal: list[float],
    lagging_signal: list[float],
    lag_days: int = 0
) -> dict:
    """
    Calculate correlation between a leading signal and lagging signal with optional lag.

    Uses Pearson correlation coefficient.
    Returns correlation value (-1 to 1) and strength assessment.
    """
    if len(leading_signal) < 5 or len(lagging_signal) < 5:
        return {"error": "Not enough data points", "correlation": 0, "strength": "insufficient_data"}

    # Apply lag - shift the lagging signal
    if lag_days > 0 and lag_days < len(lagging_signal):
        lagging_signal = lagging_signal[lag_days:]
        leading_signal = leading_signal[:len(lagging_signal)]

    # Ensure equal lengths
    min_len = min(len(leading_signal), len(lagging_signal))
    if min_len < 5:
        return {"error": "Not enough overlapping data", "correlation": 0, "strength": "insufficient_data"}

    leading = leading_signal[:min_len]
    lagging = lagging_signal[:min_len]

    # Calculate Pearson correlation
    n = len(leading)
    sum_x = sum(leading)
    sum_y = sum(lagging)
    sum_xy = sum(x * y for x, y in zip(leading, lagging))
    sum_x2 = sum(x * x for x in leading)
    sum_y2 = sum(y * y for y in lagging)

    numerator = n * sum_xy - sum_x * sum_y
    denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

    if denominator == 0:
        return {"correlation": 0, "strength": "no_variance", "lag_days": lag_days}

    correlation = numerator / denominator

    # Assess strength
    abs_corr = abs(correlation)
    if abs_corr >= 0.7:
        strength = "strong"
    elif abs_corr >= 0.4:
        strength = "moderate"
    elif abs_corr >= 0.2:
        strength = "weak"
    else:
        strength = "negligible"

    direction = "positive" if correlation > 0 else "negative"

    return {
        "correlation": round(correlation, 3),
        "strength": strength,
        "direction": direction,
        "lag_days": lag_days,
        "data_points": n,
    }


def get_weekly_metrics(days: int = 60) -> list[dict]:
    """
    Get weekly aggregated metrics for correlation analysis.

    Returns a list of weekly buckets with averaged metrics.
    """
    historical = get_kendall_historical()
    if not historical:
        return []

    metrics_list = historical.get("metrics", [])
    if not metrics_list:
        return []

    # Get date range
    now = datetime.now(EST)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    # Filter and sort by date
    filtered = [
        m for m in metrics_list
        if m.get("date", "") >= cutoff
    ]
    filtered.sort(key=lambda x: x.get("date", ""))

    if not filtered:
        return []

    # Get branded search data
    gsc_data = get_gsc_daily_trend() or []
    branded_by_date = {
        d.get("date", ""): d.get("branded_clicks", 0)
        for d in gsc_data
    }

    # Group into weeks
    weeks = []
    current_week = []
    week_start = None

    for m in filtered:
        date_str = m.get("date", "")
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        if week_start is None:
            week_start = date

        if (date - week_start).days >= 7:
            # Process completed week
            if current_week:
                weeks.append(_aggregate_week(current_week, branded_by_date))
            current_week = [m]
            week_start = date
        else:
            current_week.append(m)

    # Add final partial week if has enough data
    if len(current_week) >= 4:
        weeks.append(_aggregate_week(current_week, branded_by_date))

    return weeks


def _aggregate_week(metrics: list[dict], branded_by_date: dict) -> dict:
    """Aggregate daily metrics into weekly totals/averages."""
    if not metrics:
        return {}

    start_date = metrics[0].get("date", "")
    end_date = metrics[-1].get("date", "")

    # Sum metrics
    total_revenue = sum(m.get("sales", 0) for m in metrics)
    total_orders = sum(m.get("orders", 0) for m in metrics)
    total_nc_orders = sum(m.get("nc_orders", 0) for m in metrics)
    total_spend = sum(m.get("spend", 0) for m in metrics)
    total_meta_spend = sum(m.get("facebook_spend", 0) for m in metrics)
    total_amazon = sum(m.get("amz_us_sales", 0) for m in metrics)

    # Get branded clicks for dates in this week
    branded_clicks = sum(
        branded_by_date.get(m.get("date", ""), 0)
        for m in metrics
    )

    # Averages
    avg_mer = sum(m.get("mer", 0) for m in metrics) / len(metrics)
    avg_ncac = sum(m.get("ncac", 0) for m in metrics) / len(metrics)

    return {
        "week_start": start_date,
        "week_end": end_date,
        "days": len(metrics),
        "revenue": round(total_revenue, 2),
        "orders": total_orders,
        "new_customers": total_nc_orders,
        "ad_spend": round(total_spend, 2),
        "meta_spend": round(total_meta_spend, 2),
        "amazon_sales": round(total_amazon, 2),
        "branded_clicks": branded_clicks,
        "mer": round(avg_mer, 2),
        "ncac": round(avg_ncac, 2),
    }


def analyze_signal_predictiveness(days: int = 60) -> dict:
    """
    Analyze which leading signals actually predict revenue.

    Tests correlations between:
    - Branded search → Revenue (with various lags)
    - Amazon sales → Shopify revenue (with various lags)
    - Meta spend → Revenue (with various lags)
    - New customers → Revenue (with various lags)

    Returns correlation strengths and recommended weight adjustments.
    """
    weeks = get_weekly_metrics(days)

    if len(weeks) < 4:
        return {
            "error": "Need at least 4 weeks of data for correlation analysis",
            "weeks_available": len(weeks),
        }

    # Extract signals as lists
    revenues = [w.get("revenue", 0) for w in weeks]
    branded = [w.get("branded_clicks", 0) for w in weeks]
    amazon = [w.get("amazon_sales", 0) for w in weeks]
    new_customers = [w.get("new_customers", 0) for w in weeks]
    meta_spend = [w.get("meta_spend", 0) for w in weeks]

    # Analyze correlations with different lags
    results = {
        "branded_search_to_revenue": {},
        "amazon_to_shopify_revenue": {},
        "new_customers_to_revenue": {},
        "meta_spend_to_revenue": {},
    }

    # Branded search → Revenue
    for lag in LAG_PERIODS:
        if lag == 0:
            # For lag=0, use same-week correlation (leading indicator moves with outcome)
            corr = calculate_signal_correlation(branded, revenues, lag_days=0)
        else:
            # For lag>0, see if THIS week's branded predicts FUTURE revenue
            # Shift revenues forward (so we're comparing earlier branded to later revenue)
            corr = calculate_signal_correlation(branded[:-lag] if lag else branded, revenues[lag:] if lag else revenues, lag_days=0)
        results["branded_search_to_revenue"][f"lag_{lag}d"] = corr

    # Amazon → Shopify Revenue (looking for halo effect)
    for lag in LAG_PERIODS:
        if lag == 0:
            corr = calculate_signal_correlation(amazon, revenues, lag_days=0)
        else:
            corr = calculate_signal_correlation(amazon[:-lag] if lag else amazon, revenues[lag:] if lag else revenues, lag_days=0)
        results["amazon_to_shopify_revenue"][f"lag_{lag}d"] = corr

    # New Customers → Revenue (NC today = revenue tomorrow?)
    for lag in LAG_PERIODS:
        if lag == 0:
            corr = calculate_signal_correlation(new_customers, revenues, lag_days=0)
        else:
            corr = calculate_signal_correlation(new_customers[:-lag] if lag else new_customers, revenues[lag:] if lag else revenues, lag_days=0)
        results["new_customers_to_revenue"][f"lag_{lag}d"] = corr

    # Meta Spend → Revenue (is spend driving revenue?)
    for lag in LAG_PERIODS:
        if lag == 0:
            corr = calculate_signal_correlation(meta_spend, revenues, lag_days=0)
        else:
            corr = calculate_signal_correlation(meta_spend[:-lag] if lag else meta_spend, revenues[lag:] if lag else revenues, lag_days=0)
        results["meta_spend_to_revenue"][f"lag_{lag}d"] = corr

    # Find best predictive lag for each signal
    best_lags = {}
    for signal_name, lag_results in results.items():
        best_lag = max(
            lag_results.items(),
            key=lambda x: abs(x[1].get("correlation", 0)) if "error" not in x[1] else 0
        )
        best_lags[signal_name] = {
            "lag": best_lag[0],
            "correlation": best_lag[1].get("correlation", 0),
            "strength": best_lag[1].get("strength", "unknown"),
        }

    # Generate weight suggestions based on observed predictiveness
    weight_suggestions = _calculate_weight_suggestions(results, best_lags)

    # Save for future reference
    correlation_data = _load_correlation_data()
    correlation_data["correlations"] = results
    correlation_data["best_lags"] = best_lags
    correlation_data["weight_suggestions"] = weight_suggestions
    correlation_data["analysis_period_days"] = days
    correlation_data["weeks_analyzed"] = len(weeks)
    _save_correlation_data(correlation_data)

    return {
        "weeks_analyzed": len(weeks),
        "period_days": days,
        "correlations": results,
        "best_predictive_lags": best_lags,
        "weight_suggestions": weight_suggestions,
        "current_weights": {
            "revenue": 2.5,
            "new_customers": 2.5,
            "amazon": 2.0,
            "branded_search": 1.5,
            "mer": 1.0,
        },
    }


def _calculate_weight_suggestions(
    correlations: dict,
    best_lags: dict
) -> dict:
    """
    Calculate suggested weight adjustments based on observed correlations.

    Logic:
    - If a signal strongly correlates with revenue, it deserves higher weight
    - If a signal weakly correlates, consider reducing its weight
    - If correlation is negative, flag for investigation
    """
    suggestions = {}

    # Current weights
    current = {
        "revenue": 2.5,
        "new_customers": 2.5,
        "amazon": 2.0,
        "branded_search": 1.5,
        "mer": 1.0,
    }

    # Branded search weight suggestion
    branded_best = best_lags.get("branded_search_to_revenue", {})
    branded_corr = branded_best.get("correlation", 0)
    branded_strength = branded_best.get("strength", "unknown")

    if branded_strength == "strong" and branded_corr > 0:
        suggestions["branded_search"] = {
            "current": current["branded_search"],
            "suggested": min(2.5, current["branded_search"] + 0.5),
            "reason": f"Strong positive correlation ({branded_corr:.2f}) - branded search IS predictive of revenue",
            "confidence": "high",
        }
    elif branded_strength == "weak" or branded_strength == "negligible":
        suggestions["branded_search"] = {
            "current": current["branded_search"],
            "suggested": max(0.5, current["branded_search"] - 0.5),
            "reason": f"Weak/negligible correlation ({branded_corr:.2f}) - branded search may not predict revenue",
            "confidence": "medium",
        }
    elif branded_corr < 0:
        suggestions["branded_search"] = {
            "current": current["branded_search"],
            "suggested": current["branded_search"],
            "reason": f"Negative correlation ({branded_corr:.2f}) - investigate why branded search moves opposite to revenue",
            "confidence": "low",
            "flag": "investigate",
        }
    else:
        suggestions["branded_search"] = {
            "current": current["branded_search"],
            "suggested": current["branded_search"],
            "reason": f"Moderate correlation ({branded_corr:.2f}) - current weight seems appropriate",
            "confidence": "medium",
        }

    # Amazon weight suggestion
    amazon_best = best_lags.get("amazon_to_shopify_revenue", {})
    amazon_corr = amazon_best.get("correlation", 0)
    amazon_strength = amazon_best.get("strength", "unknown")

    if amazon_strength == "strong" and amazon_corr > 0:
        suggestions["amazon"] = {
            "current": current["amazon"],
            "suggested": min(3.0, current["amazon"] + 0.5),
            "reason": f"Strong positive correlation ({amazon_corr:.2f}) - Amazon and Shopify revenue move together",
            "confidence": "high",
        }
    elif amazon_strength == "weak" or amazon_strength == "negligible":
        suggestions["amazon"] = {
            "current": current["amazon"],
            "suggested": max(1.0, current["amazon"] - 0.5),
            "reason": f"Weak correlation ({amazon_corr:.2f}) - Amazon may be independent of Shopify performance",
            "confidence": "medium",
        }
    else:
        suggestions["amazon"] = {
            "current": current["amazon"],
            "suggested": current["amazon"],
            "reason": f"Moderate correlation ({amazon_corr:.2f}) - current weight appropriate",
            "confidence": "medium",
        }

    # New customers weight suggestion
    nc_best = best_lags.get("new_customers_to_revenue", {})
    nc_corr = nc_best.get("correlation", 0)
    nc_strength = nc_best.get("strength", "unknown")

    if nc_strength == "strong" and nc_corr > 0:
        suggestions["new_customers"] = {
            "current": current["new_customers"],
            "suggested": min(3.0, current["new_customers"] + 0.5),
            "reason": f"Strong positive correlation ({nc_corr:.2f}) - new customer acquisition drives revenue",
            "confidence": "high",
        }
    elif nc_strength == "weak" or nc_strength == "negligible":
        suggestions["new_customers"] = {
            "current": current["new_customers"],
            "suggested": max(1.5, current["new_customers"] - 0.5),
            "reason": f"Weak correlation ({nc_corr:.2f}) - may need more repeat purchase focus",
            "confidence": "medium",
        }
    else:
        suggestions["new_customers"] = {
            "current": current["new_customers"],
            "suggested": current["new_customers"],
            "reason": f"Moderate correlation ({nc_corr:.2f}) - growth mode weight appropriate",
            "confidence": "medium",
        }

    return suggestions


def get_correlation_insights_for_llm() -> str:
    """
    Build a text summary of correlation insights for the LLM prompt.

    Helps Claude understand which signals are actually predictive
    and adjust recommendations accordingly.
    """
    analysis = analyze_signal_predictiveness(days=60)

    if "error" in analysis:
        return f"Correlation analysis not available: {analysis['error']}"

    lines = []
    lines.append("## Signal Predictiveness Analysis")
    lines.append(f"*Based on {analysis['weeks_analyzed']} weeks of data*")
    lines.append("")

    # Best predictive signals
    lines.append("### Which Signals Actually Predict Revenue?")
    lines.append("")

    best_lags = analysis.get("best_predictive_lags", {})

    for signal_name, lag_data in best_lags.items():
        readable_name = signal_name.replace("_to_", " → ").replace("_", " ").title()
        corr = lag_data.get("correlation", 0)
        strength = lag_data.get("strength", "unknown")
        lag = lag_data.get("lag", "unknown")

        direction = "positively" if corr > 0 else "negatively" if corr < 0 else "not"

        lines.append(f"- **{readable_name}**: {strength} ({corr:+.2f}) - {direction} correlated")

    lines.append("")

    # Weight suggestions
    weight_suggestions = analysis.get("weight_suggestions", {})
    if weight_suggestions:
        lines.append("### Suggested Weight Adjustments")
        lines.append("*Based on observed predictiveness*")
        lines.append("")

        for signal, suggestion in weight_suggestions.items():
            current = suggestion.get("current", 0)
            suggested = suggestion.get("suggested", 0)
            reason = suggestion.get("reason", "")
            confidence = suggestion.get("confidence", "")

            if current != suggested:
                change = "↑" if suggested > current else "↓"
                lines.append(f"- **{signal.replace('_', ' ').title()}**: {current}x → {suggested}x {change}")
                lines.append(f"  - {reason}")
                lines.append(f"  - Confidence: {confidence}")
            else:
                lines.append(f"- **{signal.replace('_', ' ').title()}**: Keep at {current}x")
                lines.append(f"  - {reason}")

    lines.append("")
    lines.append("*Use these insights to weight your recommendations appropriately.*")

    return "\n".join(lines)
