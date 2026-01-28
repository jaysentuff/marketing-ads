"""
Data loading utilities for the TuffWraps API.

Reads JSON files from the connectors/data directory.
Supports multiple timeframes for analysis (1, 3, 7, 14, 30 days).
Uses direct Amazon API for real-time Amazon sales data.
"""

import json
import sys
import time
from functools import wraps
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
from zoneinfo import ZoneInfo

# EST timezone for consistent date handling
EST = ZoneInfo("America/New_York")

# =============================================================================
# CACHING SYSTEM - Eliminates redundant file reads and computations
# =============================================================================

# Global cache storage
_cache: dict[str, tuple[Any, float]] = {}

# TTL settings (in seconds)
CACHE_TTL_JSON = 300      # 5 minutes for JSON file loads
CACHE_TTL_COMPUTED = 600  # 10 minutes for computed summaries
CACHE_TTL_HEAVY = 900     # 15 minutes for heavy computations


def cached(ttl: int = CACHE_TTL_JSON):
    """
    Decorator that caches function results with TTL.
    Cache key is based on function name and arguments.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and args
            key_parts = [func.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            now = time.time()

            # Check cache
            if cache_key in _cache:
                cached_value, cached_time = _cache[cache_key]
                if now - cached_time < ttl:
                    return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, now)
            return result
        return wrapper
    return decorator


def clear_cache():
    """Clear all cached data. Call after daily data pull."""
    global _cache
    _cache.clear()
    print("[Cache] All caches cleared")

# Add connectors directory to path for Amazon API access
CONNECTORS_DIR = Path(__file__).parent.parent.parent / "connectors"
sys.path.insert(0, str(CONNECTORS_DIR))

# Load connectors .env file for Amazon API credentials
from dotenv import load_dotenv
load_dotenv(CONNECTORS_DIR / ".env")

# Amazon API cache - 24 hour TTL (data only changes with 8 AM daily pull)
_amazon_cache: dict = {}
_amazon_cache_ttl = 86400  # 24 hours in seconds
_amazon_rate_limited_until = 0  # Timestamp when rate limit expires


# Data directory path - relative to backend folder
DATA_DIR = Path(__file__).parent.parent.parent / "connectors" / "data"

# Valid timeframe options
VALID_TIMEFRAMES = [1, 2, 3, 7, 14, 30]

# Operational reminders config
SHIPPING_REMINDER_FILE = DATA_DIR / "operational" / "shipping_reminder.json"
SHIPPING_REMINDER_DAYS = 60  # Remind every 60 days to check ShipStation

# Keywords that identify TOF campaigns (case-insensitive)
TOF_KEYWORDS = ["tof", "prospecting", "awareness", "top of funnel", "cold", "discovery"]


def is_tof_campaign(campaign_name: str) -> bool:
    """Check if a campaign is a TOF (Top-of-Funnel) campaign."""
    name_lower = campaign_name.lower()
    return any(kw in name_lower for kw in TOF_KEYWORDS)


def load_json(filepath: Path) -> Optional[dict | list]:
    """Load a JSON file, returning None if not found."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json(filepath: Path, data: dict | list) -> bool:
    """Save data to a JSON file."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False


@cached(ttl=CACHE_TTL_JSON)
def get_latest_report() -> Optional[dict]:
    """Get the latest CAM report."""
    return load_json(DATA_DIR / "aggregated" / "latest_report.json")


@cached(ttl=CACHE_TTL_JSON)
def get_kendall_attribution() -> Optional[dict]:
    """Get Kendall attribution by source data."""
    return load_json(DATA_DIR / "kendall" / "attribution_by_source.json")


@cached(ttl=CACHE_TTL_JSON)
def get_kendall_pnl() -> Optional[dict]:
    """Get Kendall profit/loss data."""
    return load_json(DATA_DIR / "kendall" / "profit_loss.json")


@cached(ttl=CACHE_TTL_JSON)
def get_kendall_historical() -> Optional[dict]:
    """Get Kendall historical metrics including first-click attribution."""
    return load_json(DATA_DIR / "kendall" / "historical_metrics.json")


@cached(ttl=CACHE_TTL_JSON)
def get_gsc_branded() -> Optional[dict]:
    """Get Google Search Console branded vs non-branded data."""
    return load_json(DATA_DIR / "gsc" / "branded_vs_nonbranded.json")


@cached(ttl=CACHE_TTL_JSON)
def get_gsc_daily_trend() -> Optional[list]:
    """Get GSC daily branded search trend."""
    return load_json(DATA_DIR / "gsc" / "daily_branded_trend.json")


@cached(ttl=CACHE_TTL_JSON)
def get_shopify_metrics() -> Optional[dict]:
    """Get Shopify metrics."""
    return load_json(DATA_DIR / "shopify" / "metrics_last_30d.json")


@cached(ttl=CACHE_TTL_JSON)
def get_google_ads_campaigns() -> Optional[list]:
    """Get Google Ads campaign data."""
    return load_json(DATA_DIR / "google_ads" / "campaigns_last_30d.json")


@cached(ttl=CACHE_TTL_JSON)
def get_meta_ads_campaigns() -> Optional[list]:
    """Get Meta Ads campaign data."""
    return load_json(DATA_DIR / "meta_ads" / "campaigns_last_30d.json")


@cached(ttl=CACHE_TTL_JSON)
def get_ga4_summary() -> Optional[dict]:
    """Get GA4 summary data."""
    return load_json(DATA_DIR / "ga4" / "summary_last_30d.json")


@cached(ttl=CACHE_TTL_JSON)
def get_ga4_traffic() -> Optional[list]:
    """Get GA4 daily traffic data."""
    return load_json(DATA_DIR / "ga4" / "daily_traffic.json")


@cached(ttl=CACHE_TTL_JSON)
def get_klaviyo_summary() -> Optional[dict]:
    """Get Klaviyo summary data."""
    return load_json(DATA_DIR / "klaviyo" / "summary_last_30d.json")


def _fetch_and_cache_all_amazon_data() -> bool:
    """
    Fetch 7 days of Amazon orders and cache metrics for all timeframes.
    Returns True if successful, False otherwise.
    """
    global _amazon_cache, _amazon_rate_limited_until

    now = datetime.now().timestamp()

    # Check if we're rate limited
    if now < _amazon_rate_limited_until:
        return False

    try:
        from amazon_seller import AmazonSellerConnector
        import pytz

        connector = AmazonSellerConnector()
        if not connector.configured:
            print("[Amazon] Connector not configured")
            return False

        print("[Amazon] Fetching 7 days of orders (single API call)...")

        # Use EST timezone
        est = pytz.timezone("US/Eastern")
        now_est = datetime.now(est)

        # Fetch 7 days of orders
        end_date = (now_est - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = (now_est - timedelta(days=7)).strftime("%Y-%m-%d")

        orders = connector.get_orders(start_date, end_date)

        # Parse order dates and amounts
        order_data = []
        for order in orders:
            order_date = order.get("PurchaseDate", "")[:10]  # YYYY-MM-DD
            order_total = order.get("OrderTotal", {})
            amount = float(order_total.get("Amount", 0)) if order_total else 0
            order_data.append({"date": order_date, "amount": amount})

        # Calculate metrics for each timeframe
        yesterday = (now_est - timedelta(days=1)).strftime("%Y-%m-%d")
        three_days_ago = (now_est - timedelta(days=3)).strftime("%Y-%m-%d")
        seven_days_ago = (now_est - timedelta(days=7)).strftime("%Y-%m-%d")

        for days, cutoff_date in [(1, yesterday), (3, three_days_ago), (7, seven_days_ago)]:
            filtered = [o for o in order_data if o["date"] >= cutoff_date]
            total_orders = len(filtered)
            total_sales = sum(o["amount"] for o in filtered)

            metrics = {
                "sales": round(total_sales, 2),
                "orders": total_orders,
                "avg_order_value": round(total_sales / total_orders, 2) if total_orders > 0 else 0,
            }
            _amazon_cache[f"amazon_{days}"] = (metrics, now)

        print(f"[Amazon] SUCCESS - Cached all timeframes (7d: {len(order_data)} orders, ${sum(o['amount'] for o in order_data):,.2f})")
        return True

    except Exception as e:
        error_str = str(e)
        print(f"[Amazon] Error: {error_str}")
        if "429" in error_str or "QuotaExceeded" in error_str:
            _amazon_rate_limited_until = now + 60
            print("[Amazon] Rate limited - backing off for 60 seconds")
        return False


def get_amazon_direct(days: int = 1) -> Optional[dict]:
    """
    Get Amazon sales data directly from Amazon SP-API with caching.

    This fetches all timeframes in a single API call for efficiency.
    Results are cached for 5 minutes to improve page load speed.

    Args:
        days: Number of days to fetch (1 = yesterday, 3 = 3 days, 7 = last week)

    Returns:
        Dictionary with Amazon metrics or None if API not available
    """
    global _amazon_cache, _amazon_rate_limited_until

    now = datetime.now().timestamp()
    cache_key = f"amazon_{days}"

    # Check cache first
    if cache_key in _amazon_cache:
        cached_data, cached_time = _amazon_cache[cache_key]
        if now - cached_time < _amazon_cache_ttl:
            print(f"[Amazon] Cache hit for {days} day(s)")
            return cached_data

    # Check if we're rate limited
    if now < _amazon_rate_limited_until:
        wait_time = int(_amazon_rate_limited_until - now)
        print(f"[Amazon] Rate limited (retry in {wait_time}s)")
        return None

    # Fetch and cache all timeframes at once
    if _fetch_and_cache_all_amazon_data():
        # Return from newly populated cache
        if cache_key in _amazon_cache:
            return _amazon_cache[cache_key][0]

    return None


def get_channel_campaigns(channel: str) -> list[dict]:
    """Get campaign breakdown for a specific channel."""
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

    campaigns.sort(key=lambda x: x["orders"], reverse=True)
    return campaigns


@cached(ttl=CACHE_TTL_COMPUTED)
def get_blended_metrics() -> dict:
    """Get blended metrics from Kendall historical data."""
    historical = get_kendall_historical()
    if not historical:
        return {}

    metrics_list = historical.get("metrics", [])
    if not metrics_list:
        return {}

    recent = metrics_list[-7:] if len(metrics_list) >= 7 else metrics_list
    prior = metrics_list[-14:-7] if len(metrics_list) >= 14 else []

    recent_ncac = sum(m.get("ncac", 0) for m in recent) / len(recent) if recent else 0
    recent_meta_fc = sum(m.get("facebook_fc", 0) for m in recent)
    recent_google_fc = sum(m.get("google_fc", 0) for m in recent)
    recent_amazon = sum(m.get("amz_us_sales", 0) for m in recent)

    prior_meta_fc = sum(m.get("facebook_fc", 0) for m in prior) if prior else 0
    prior_amazon = sum(m.get("amz_us_sales", 0) for m in prior) if prior else 0

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


def get_shipping_reminder_state() -> dict:
    """Get the current state of the shipping cost reminder."""
    state = load_json(SHIPPING_REMINDER_FILE)
    if not state:
        return {
            "last_checked": None,
            "last_cost": None,
            "kendall_setting": 6.87,  # Default from Kendall
        }
    return state


def update_shipping_reminder(cost: float = None, kendall_setting: float = None) -> dict:
    """Mark that shipping costs were checked and update the stored values."""
    state = get_shipping_reminder_state()
    state["last_checked"] = datetime.now().isoformat()
    if cost is not None:
        state["last_cost"] = cost
    if kendall_setting is not None:
        state["kendall_setting"] = kendall_setting
    save_json(SHIPPING_REMINDER_FILE, state)
    return state


def get_shipstation_average() -> Optional[float]:
    """Get the average shipping cost from ShipStation data file."""
    shipping_data = load_json(DATA_DIR / "shipstation" / "shipping_costs_last_30d.json")
    if shipping_data:
        return shipping_data.get("average_cost_per_shipment")
    return None


def check_shipping_reminder() -> Optional[dict]:
    """
    Check if the shipping cost reminder is due.
    Returns a reminder dict if action needed, None otherwise.
    """
    state = get_shipping_reminder_state()
    last_checked = state.get("last_checked")

    # Get current ShipStation average (if available)
    current_avg = get_shipstation_average()
    kendall_setting = state.get("kendall_setting", 6.87)

    # Check if reminder is due
    reminder_due = False
    days_since_check = None

    if last_checked:
        try:
            last_date = datetime.fromisoformat(last_checked)
            days_since_check = (datetime.now() - last_date).days
            if days_since_check >= SHIPPING_REMINDER_DAYS:
                reminder_due = True
        except (ValueError, TypeError):
            reminder_due = True
    else:
        # Never checked before
        reminder_due = True
        days_since_check = None

    if not reminder_due:
        return None

    # Build reminder message
    if current_avg:
        diff = current_avg - kendall_setting
        diff_pct = (diff / kendall_setting * 100) if kendall_setting > 0 else 0

        if abs(diff) > 0.50:  # More than $0.50 difference
            urgency = "high"
            message = (
                f"ShipStation avg is ${current_avg:.2f}, but Kendall is set to ${kendall_setting:.2f} "
                f"(${diff:+.2f}, {diff_pct:+.1f}%). Consider updating Kendall."
            )
        else:
            urgency = "low"
            message = (
                f"Time to verify shipping costs. ShipStation avg: ${current_avg:.2f}, "
                f"Kendall setting: ${kendall_setting:.2f}."
            )
    else:
        urgency = "medium"
        message = (
            f"Check ShipStation Insights for current avg shipping cost and update Kendall if needed. "
            f"Current Kendall setting: ${kendall_setting:.2f}."
        )

    return {
        "type": "shipping_cost_check",
        "urgency": urgency,
        "message": message,
        "days_since_check": days_since_check,
        "current_shipstation_avg": current_avg,
        "kendall_setting": kendall_setting,
        "action": "Check ShipStation > Insights > Operations for avg cost per label, then update Kendall Store Settings",
    }


@cached(ttl=CACHE_TTL_COMPUTED)
def get_decision_signals() -> dict:
    """Analyze current data and return decision signals."""
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
        "operational_reminders": [],
    }

    # Check for operational reminders (shipping costs, etc.)
    shipping_reminder = check_shipping_reminder()
    if shipping_reminder:
        signals["operational_reminders"].append(shipping_reminder)

    blended = get_blended_metrics()

    cam_per_order = summary.get("blended_cam_per_order", 0)
    target_cam = 20

    if cam_per_order > target_cam * 1.2:
        signals["spend_decision"] = "increase"
    elif cam_per_order < target_cam * 0.8:
        signals["spend_decision"] = "decrease"

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

                if is_tof_campaign(name):
                    tof_campaigns.append({
                        "channel": channel,
                        "name": name,
                        "orders": orders,
                        "revenue": metrics.get("sales", 0),
                        "roas": roas,
                        "nc_pct": nc_pct,
                    })
                    continue

                if orders >= 10:
                    if roas >= 3.0:
                        signals["campaigns_to_scale"].append({
                            "channel": channel,
                            "name": name,
                            "roas": roas,
                            "orders": orders,
                            "nc_pct": nc_pct,
                        })
                    elif roas > 0 and roas < 1.5 and orders >= 30:
                        signals["campaigns_to_watch"].append({
                            "channel": channel,
                            "name": name,
                            "roas": roas,
                            "orders": orders,
                            "note": "Low ROAS - review creative and targeting"
                        })

    if tof_campaigns or blended.get("meta_first_click_7d"):
        branded = r.get("branded_search", {})
        branded_pct = branded.get("branded_pct", 0)

        tof_total_orders = sum(c["orders"] for c in tof_campaigns)
        tof_total_revenue = sum(c["revenue"] for c in tof_campaigns)
        tof_avg_nc_pct = (sum(c["nc_pct"] for c in tof_campaigns) / len(tof_campaigns) * 100) if tof_campaigns else 0

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
            "message": "",
        }

        ncac = blended.get("ncac_7d_avg", 0)

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

    signals["campaigns_to_scale"].sort(key=lambda x: x["roas"], reverse=True)
    signals["campaigns_to_watch"].sort(key=lambda x: x["roas"])

    platform_vs_kendall = r.get("platform_vs_kendall", {})
    over_attribution_pct = platform_vs_kendall.get("over_attribution_pct", 0)

    if over_attribution_pct > 40:
        signals["alerts"].append(
            f"Platforms over-claiming revenue by {over_attribution_pct:.0f}%. "
            "Use Kendall attribution, not platform ROAS."
        )

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


# ============================================================================
# TIMEFRAME-BASED METRICS (for short-term analysis: 1, 3, 7, 14, 30 days)
# ============================================================================

def get_date_cutoff(days: int) -> str:
    """Get the date cutoff string for filtering data (EST timezone)."""
    now_est = datetime.now(EST)
    cutoff = now_est - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def filter_by_date(items: list, days: int, date_field: str = "date") -> list:
    """Filter a list of items by date field within the last N days."""
    cutoff = get_date_cutoff(days)
    return [item for item in items if item.get(date_field, "") >= cutoff]


@cached(ttl=CACHE_TTL_COMPUTED)
def get_historical_metrics_for_timeframe(days: int = 30) -> dict:
    """Get aggregated metrics from historical data for a specific timeframe."""
    historical = get_kendall_historical()
    if not historical:
        return {}

    metrics_list = historical.get("metrics", [])
    if not metrics_list:
        return {}

    # Filter by date
    filtered = filter_by_date(metrics_list, days)
    if not filtered:
        return {}

    # Aggregate key metrics
    total_sales = sum(m.get("sales", 0) for m in filtered)
    total_orders = sum(m.get("orders", 0) for m in filtered)
    total_nc_orders = sum(m.get("nc_orders", 0) for m in filtered)
    total_spend = sum(m.get("spend", 0) for m in filtered)
    total_cam = sum(m.get("contrib_after_mkt", 0) for m in filtered)

    # Amazon metrics - prefer direct API data, fall back to Kendall
    amazon_direct = get_amazon_direct(days)
    amazon_data_source = "api"

    if amazon_direct:
        amazon_sales = amazon_direct.get("sales", 0)
        amazon_orders = amazon_direct.get("orders", 0)
    else:
        # Fall back to Kendall data
        amazon_data_source = "kendall"
        amazon_sales = sum(m.get("amz_us_sales", 0) for m in filtered)
        amazon_orders = sum(m.get("amazon_na_orders", 0) for m in filtered)

    # Amazon ad spend still comes from Kendall (SP-API doesn't provide this easily)
    amazon_spend = sum(m.get("amazon_spend", 0) for m in filtered)

    # Meta TOF metrics for correlation
    meta_first_click = sum(m.get("facebook_fc", 0) for m in filtered)
    meta_spend = sum(m.get("facebook_spend", 0) for m in filtered)

    # Calculate averages and derived metrics
    cam_per_order = total_cam / total_orders if total_orders > 0 else 0
    avg_ncac = sum(m.get("ncac", 0) for m in filtered) / len(filtered) if filtered else 0
    blended_roas = total_sales / total_spend if total_spend > 0 else 0

    return {
        "days": days,
        "total_sales": total_sales,
        "total_orders": total_orders,
        "total_nc_orders": total_nc_orders,
        "total_spend": total_spend,
        "total_cam": total_cam,
        "cam_per_order": cam_per_order,
        "avg_ncac": avg_ncac,
        "blended_roas": blended_roas,
        "data_points": len(filtered),
        "daily_metrics": filtered,
        # Amazon data (from direct API when available)
        "amazon_sales": amazon_sales,
        "amazon_orders": amazon_orders,
        "amazon_spend": amazon_spend,
        "amazon_roas": amazon_sales / amazon_spend if amazon_spend > 0 else 0,
        "amazon_data_source": amazon_data_source,
        # Meta TOF data for correlation
        "meta_first_click": meta_first_click,
        "meta_spend": meta_spend,
    }


def get_google_campaigns_for_timeframe(days: int = 30) -> list:
    """Get Google Ads campaigns aggregated for the specified timeframe."""
    campaigns = get_google_ads_campaigns()
    if not campaigns:
        return []

    filtered = filter_by_date(campaigns, days)

    # Aggregate by campaign
    campaign_totals = {}
    for c in filtered:
        name = c.get("campaign_name", "Unknown")
        if name not in campaign_totals:
            campaign_totals[name] = {
                "name": name,
                "campaign_id": c.get("campaign_id"),
                "channel_type": c.get("channel_type"),
                "status": c.get("campaign_status"),
                "spend": 0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "conversion_value": 0,
                "days_active": 0,
            }
        campaign_totals[name]["spend"] += c.get("spend", 0)
        campaign_totals[name]["impressions"] += c.get("impressions", 0)
        campaign_totals[name]["clicks"] += c.get("clicks", 0)
        campaign_totals[name]["conversions"] += c.get("conversions", 0)
        campaign_totals[name]["conversion_value"] += c.get("conversion_value", 0)
        campaign_totals[name]["days_active"] += 1

    # Calculate derived metrics
    result = []
    for camp in campaign_totals.values():
        spend = camp["spend"]
        value = camp["conversion_value"]
        clicks = camp["clicks"]
        impressions = camp["impressions"]

        camp["roas"] = value / spend if spend > 0 else 0
        camp["cpc"] = spend / clicks if clicks > 0 else 0
        camp["ctr"] = (clicks / impressions * 100) if impressions > 0 else 0
        result.append(camp)

    result.sort(key=lambda x: x["spend"], reverse=True)
    return result


def get_meta_campaigns_for_timeframe(days: int = 30) -> list:
    """Get Meta Ads campaigns aggregated for the specified timeframe."""
    campaigns = get_meta_ads_campaigns()
    if not campaigns:
        return []

    filtered = filter_by_date(campaigns, days)

    # Aggregate by campaign
    campaign_totals = {}
    for c in filtered:
        name = c.get("campaign_name", "Unknown")
        if name not in campaign_totals:
            campaign_totals[name] = {
                "name": name,
                "campaign_id": c.get("campaign_id"),
                "objective": c.get("objective"),
                "spend": 0,
                "impressions": 0,
                "clicks": 0,
                "reach": 0,
                "purchases": 0,
                "purchase_value": 0,
                "days_active": 0,
            }
        campaign_totals[name]["spend"] += c.get("spend", 0)
        campaign_totals[name]["impressions"] += c.get("impressions", 0)
        campaign_totals[name]["clicks"] += c.get("clicks", 0)
        campaign_totals[name]["reach"] += c.get("reach", 0)
        campaign_totals[name]["purchases"] += c.get("purchases", 0)
        campaign_totals[name]["purchase_value"] += c.get("purchase_value", 0)
        campaign_totals[name]["days_active"] += 1

    # Calculate derived metrics
    result = []
    for camp in campaign_totals.values():
        spend = camp["spend"]
        value = camp["purchase_value"]
        clicks = camp["clicks"]
        impressions = camp["impressions"]

        camp["roas"] = value / spend if spend > 0 else 0
        camp["cpc"] = spend / clicks if clicks > 0 else 0
        camp["ctr"] = (clicks / impressions * 100) if impressions > 0 else 0
        result.append(camp)

    result.sort(key=lambda x: x["spend"], reverse=True)
    return result


def get_halo_effect_trend(days: int = 30) -> dict:
    """
    Get daily ad spend vs Amazon sales data for halo effect correlation chart.
    Returns time series data showing the relationship between marketing spend
    and Amazon sales over time.
    """
    historical = get_kendall_historical()
    if not historical:
        return {"data": [], "summary": {}}

    metrics_list = historical.get("metrics", [])
    if not metrics_list:
        return {"data": [], "summary": {}}

    # Filter by date
    filtered = filter_by_date(metrics_list, days)
    if not filtered:
        return {"data": [], "summary": {}}

    # Extract daily data points for the chart
    daily_data = []
    for m in filtered:
        daily_data.append({
            "date": m.get("date", ""),
            "total_spend": m.get("spend", 0),
            "meta_spend": m.get("facebook_spend", 0),
            "google_spend": m.get("google_spend", 0),
            "amazon_sales": m.get("amz_us_sales", 0),
            "shopify_sales": m.get("sales", 0),
            "meta_first_click": m.get("facebook_fc", 0),
        })

    # Sort by date
    daily_data.sort(key=lambda x: x["date"])

    # Calculate summary statistics
    total_spend = sum(d["total_spend"] for d in daily_data)
    total_amazon = sum(d["amazon_sales"] for d in daily_data)
    total_shopify = sum(d["shopify_sales"] for d in daily_data)

    # Calculate correlation coefficient (simple Pearson)
    if len(daily_data) >= 3:
        spends = [d["total_spend"] for d in daily_data]
        amazons = [d["amazon_sales"] for d in daily_data]

        n = len(spends)
        sum_x = sum(spends)
        sum_y = sum(amazons)
        sum_xy = sum(x * y for x, y in zip(spends, amazons))
        sum_x2 = sum(x * x for x in spends)
        sum_y2 = sum(y * y for y in amazons)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

        correlation = numerator / denominator if denominator > 0 else 0
    else:
        correlation = 0

    return {
        "data": daily_data,
        "summary": {
            "days": days,
            "data_points": len(daily_data),
            "total_ad_spend": total_spend,
            "total_amazon_sales": total_amazon,
            "total_shopify_sales": total_shopify,
            "spend_amazon_correlation": round(correlation, 3),
            "correlation_strength": (
                "Strong positive" if correlation > 0.7 else
                "Moderate positive" if correlation > 0.4 else
                "Weak positive" if correlation > 0.1 else
                "Neutral" if correlation > -0.1 else
                "Weak negative" if correlation > -0.4 else
                "Moderate negative" if correlation > -0.7 else
                "Strong negative"
            ),
        }
    }


@cached(ttl=CACHE_TTL_HEAVY)
def get_spend_outcome_correlation(days: int = 14) -> dict:
    """
    Analyze the correlation between ad spend changes and actual business outcomes.

    This is the core triangulation function - it doesn't trust any attribution model.
    Instead, it answers: "When spend changed, what happened to actual sales?"

    Returns signal agreement analysis showing whether multiple metrics moved together.
    """
    historical = get_kendall_historical()
    if not historical:
        return {"error": "No historical data available"}

    metrics_list = historical.get("metrics", [])
    if len(metrics_list) < days * 2:
        return {"error": f"Need at least {days * 2} days of data for comparison"}

    # Get current period and previous period
    cutoff_current = get_date_cutoff(days)
    cutoff_prev = get_date_cutoff(days * 2)

    current_period = [m for m in metrics_list if m.get("date", "") >= cutoff_current]
    prev_period = [m for m in metrics_list if cutoff_prev <= m.get("date", "") < cutoff_current]

    if not current_period or not prev_period:
        return {"error": "Not enough data for comparison period"}

    # Calculate totals for each period
    def sum_metrics(period: list) -> dict:
        # Use Kendall's MER and NCAC directly (average of daily values)
        # This matches what Kendall shows in their UI
        avg_mer = sum(m.get("mer", 0) for m in period) / len(period) if period else 0
        avg_ncac = sum(m.get("ncac", 0) for m in period) / len(period) if period else 0

        return {
            "ad_spend": sum(m.get("spend", 0) for m in period),
            "google_spend": sum(m.get("google_spend", 0) for m in period),
            "meta_spend": sum(m.get("facebook_spend", 0) for m in period),
            "amazon_spend": sum(m.get("amazon_spend", 0) for m in period),
            "shopify_revenue": sum(m.get("sales", 0) for m in period),
            "shopify_orders": sum(m.get("orders", 0) for m in period),
            "new_customers": sum(m.get("nc_orders", 0) for m in period),
            "amazon_sales": sum(m.get("amz_us_sales", 0) for m in period),
            "meta_first_click": sum(m.get("facebook_fc", 0) for m in period),
            "cam": sum(m.get("contrib_after_mkt", 0) for m in period),
            # Use Kendall's pre-calculated efficiency metrics
            "mer": avg_mer,
            "ncac": avg_ncac,
        }

    current = sum_metrics(current_period)
    previous = sum_metrics(prev_period)

    # Calculate percentage changes
    def pct_change(curr: float, prev: float) -> float:
        if prev == 0:
            return 0 if curr == 0 else 100
        return ((curr - prev) / prev) * 100

    changes = {
        "ad_spend": pct_change(current["ad_spend"], previous["ad_spend"]),
        "google_spend": pct_change(current["google_spend"], previous["google_spend"]),
        "meta_spend": pct_change(current["meta_spend"], previous["meta_spend"]),
        "shopify_revenue": pct_change(current["shopify_revenue"], previous["shopify_revenue"]),
        "shopify_orders": pct_change(current["shopify_orders"], previous["shopify_orders"]),
        "new_customers": pct_change(current["new_customers"], previous["new_customers"]),
        "amazon_sales": pct_change(current["amazon_sales"], previous["amazon_sales"]),
        "meta_first_click": pct_change(current["meta_first_click"], previous["meta_first_click"]),
        "cam": pct_change(current["cam"], previous["cam"]),
    }

    # Get branded search data if available
    gsc_data = get_gsc_daily_trend()
    branded_search_change = 0
    if gsc_data and len(gsc_data) >= days * 2:
        gsc_sorted = sorted(gsc_data, key=lambda x: x.get("date", ""))
        current_branded = sum(d.get("branded_clicks", 0) for d in gsc_sorted[-days:])
        prev_branded = sum(d.get("branded_clicks", 0) for d in gsc_sorted[-days*2:-days])
        branded_search_change = pct_change(current_branded, prev_branded)

    changes["branded_search"] = branded_search_change

    # Signal analysis - did metrics move in same direction as spend?
    spend_direction = "up" if changes["ad_spend"] > 2 else "down" if changes["ad_spend"] < -2 else "flat"

    signals = []

    # Check each outcome signal
    outcome_metrics = [
        ("shopify_revenue", "Shopify Revenue", changes["shopify_revenue"]),
        ("new_customers", "New Customers", changes["new_customers"]),
        ("amazon_sales", "Amazon Sales", changes["amazon_sales"]),
        ("branded_search", "Branded Search", changes["branded_search"]),
    ]

    for key, label, change in outcome_metrics:
        metric_direction = "up" if change > 2 else "down" if change < -2 else "flat"

        if spend_direction == "flat":
            agreement = "neutral"
        elif spend_direction == metric_direction:
            agreement = "agree"
        elif metric_direction == "flat":
            agreement = "neutral"
        else:
            agreement = "disagree"

        signals.append({
            "metric": key,
            "label": label,
            "change_pct": round(change, 1),
            "direction": metric_direction,
            "agreement": agreement,
        })

    # Count agreements
    agree_count = sum(1 for s in signals if s["agreement"] == "agree")
    disagree_count = sum(1 for s in signals if s["agreement"] == "disagree")

    # Use Kendall's MER and NCAC values directly (already averaged in sum_metrics)
    current_mer = current["mer"]
    previous_mer = previous["mer"]
    mer_change = pct_change(current_mer, previous_mer)

    current_ncac = current["ncac"]
    previous_ncac = previous["ncac"]
    ncac_change = pct_change(current_ncac, previous_ncac)

    # Determine overall verdict
    if spend_direction == "up":
        if agree_count >= 3:
            verdict = "confident"
            verdict_message = f"Spend increase is working. {agree_count}/4 signals moved up with spend."
        elif agree_count >= 2:
            verdict = "likely_working"
            verdict_message = f"Spend increase appears to be working. {agree_count}/4 signals agree."
        elif disagree_count >= 2:
            verdict = "concerning"
            verdict_message = f"Spend increased but {disagree_count}/4 key metrics declined. Review efficiency."
        else:
            verdict = "inconclusive"
            verdict_message = "Mixed signals. Need more data or time for effects to show."
    elif spend_direction == "down":
        if changes["shopify_revenue"] < -2 and changes["new_customers"] < -2:
            verdict = "expected_decline"
            verdict_message = "Sales declining as expected with reduced spend."
        elif changes["shopify_revenue"] > 2:
            verdict = "efficient"
            verdict_message = "Spend cut but revenue held/grew. Previous spend may have been wasteful."
        else:
            verdict = "monitoring"
            verdict_message = "Spend reduced. Monitor for delayed effects."
    else:
        verdict = "stable"
        verdict_message = "Spend stable. Watch for trends over time."

    # Build daily trend data for charts
    daily_trend = []
    for m in current_period:
        daily_trend.append({
            "date": m.get("date", ""),
            "ad_spend": m.get("spend", 0),
            "shopify_revenue": m.get("sales", 0),
            "new_customers": m.get("nc_orders", 0),
            "amazon_sales": m.get("amz_us_sales", 0),
        })

    return {
        "period": {
            "days": days,
            "current_start": cutoff_current,
            "previous_start": cutoff_prev,
            "label": f"Last {days} days vs previous {days} days",
        },
        "current_totals": {
            "ad_spend": round(current["ad_spend"], 2),
            "shopify_revenue": round(current["shopify_revenue"], 2),
            "shopify_orders": current["shopify_orders"],
            "new_customers": current["new_customers"],
            "amazon_sales": round(current["amazon_sales"], 2),
            "mer": round(current_mer, 2),
            "ncac": round(current_ncac, 2),
        },
        "previous_totals": {
            "ad_spend": round(previous["ad_spend"], 2),
            "shopify_revenue": round(previous["shopify_revenue"], 2),
            "shopify_orders": previous["shopify_orders"],
            "new_customers": previous["new_customers"],
            "amazon_sales": round(previous["amazon_sales"], 2),
            "mer": round(previous_mer, 2),
            "ncac": round(previous_ncac, 2),
        },
        "changes": {
            "ad_spend_pct": round(changes["ad_spend"], 1),
            "shopify_revenue_pct": round(changes["shopify_revenue"], 1),
            "new_customers_pct": round(changes["new_customers"], 1),
            "amazon_sales_pct": round(changes["amazon_sales"], 1),
            "branded_search_pct": round(changes["branded_search"], 1),
            "mer_pct": round(mer_change, 1),
            "ncac_pct": round(ncac_change, 1),
        },
        "spend_direction": spend_direction,
        "signals": signals,
        "signal_summary": {
            "agree": agree_count,
            "disagree": disagree_count,
            "neutral": 4 - agree_count - disagree_count,
        },
        "efficiency": {
            "current_mer": round(current_mer, 2),
            "previous_mer": round(previous_mer, 2),
            "mer_change_pct": round(mer_change, 1),
            "current_ncac": round(current_ncac, 2),
            "previous_ncac": round(previous_ncac, 2),
            "ncac_change_pct": round(ncac_change, 1),
            "note": "MER = Revenue/Spend (higher is better). NCAC = Spend/New Customers (lower is better).",
        },
        "verdict": {
            "status": verdict,
            "message": verdict_message,
        },
        "daily_trend": daily_trend,
    }


@cached(ttl=CACHE_TTL_HEAVY)
def get_channel_correlation(days: int = 14) -> dict:
    """
    Break down spend-to-outcome correlation by channel (Google vs Meta).

    This helps answer: "Which platform's spend changes correlate better with outcomes?"
    """
    historical = get_kendall_historical()
    if not historical:
        return {"error": "No historical data available"}

    metrics_list = historical.get("metrics", [])
    if len(metrics_list) < days * 2:
        return {"error": f"Need at least {days * 2} days of data"}

    cutoff_current = get_date_cutoff(days)
    cutoff_prev = get_date_cutoff(days * 2)

    current_period = [m for m in metrics_list if m.get("date", "") >= cutoff_current]
    prev_period = [m for m in metrics_list if cutoff_prev <= m.get("date", "") < cutoff_current]

    if not current_period or not prev_period:
        return {"error": "Not enough data"}

    def analyze_channel(spend_key: str, channel_name: str) -> dict:
        curr_spend = sum(m.get(spend_key, 0) for m in current_period)
        prev_spend = sum(m.get(spend_key, 0) for m in prev_period)

        curr_revenue = sum(m.get("sales", 0) for m in current_period)
        prev_revenue = sum(m.get("sales", 0) for m in prev_period)

        curr_nc = sum(m.get("nc_orders", 0) for m in current_period)
        prev_nc = sum(m.get("nc_orders", 0) for m in prev_period)

        spend_change = ((curr_spend - prev_spend) / prev_spend * 100) if prev_spend > 0 else 0
        revenue_change = ((curr_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
        nc_change = ((curr_nc - prev_nc) / prev_nc * 100) if prev_nc > 0 else 0

        # Correlation score: how well does spend change predict outcome change?
        # If both move same direction and similar magnitude, score is high
        if spend_change != 0:
            revenue_correlation = min(100, max(-100, (revenue_change / abs(spend_change)) * 100))
            nc_correlation = min(100, max(-100, (nc_change / abs(spend_change)) * 100))
        else:
            revenue_correlation = 0
            nc_correlation = 0

        return {
            "channel": channel_name,
            "current_spend": round(curr_spend, 2),
            "previous_spend": round(prev_spend, 2),
            "spend_change_pct": round(spend_change, 1),
            "revenue_change_pct": round(revenue_change, 1),
            "new_customer_change_pct": round(nc_change, 1),
            "revenue_correlation": round(revenue_correlation, 1),
            "nc_correlation": round(nc_correlation, 1),
        }

    google = analyze_channel("google_spend", "Google Ads")
    meta = analyze_channel("facebook_spend", "Meta Ads")

    return {
        "period": {
            "days": days,
            "label": f"Last {days} days vs previous {days} days",
        },
        "channels": {
            "google": google,
            "meta": meta,
        },
        "recommendation": None,  # Will be set based on analysis
    }


@cached(ttl=CACHE_TTL_HEAVY)
def get_recently_actioned_items(days: int = 7) -> set:
    """Get channels/campaigns that have been actioned recently."""
    from services.changelog import get_recent_entries
    entries = get_recent_entries(days=days, limit=100)
    actioned = set()
    for entry in entries:
        # Track by channel for channel-level recommendations
        channel = entry.get("channel", "")
        if channel:
            # Normalize channel names
            if "meta" in channel.lower():
                actioned.add("Meta")
            if "google" in channel.lower():
                actioned.add("Google")
        # Track by campaign name for specific campaign recommendations
        campaign = entry.get("campaign", "")
        if campaign:
            actioned.add(campaign)
            # Handle partial matches
            if len(campaign) > 10:
                actioned.add(campaign[:50])
    return actioned


def get_budget_recommendations(days: int = 7) -> dict:
    """
    Generate actionable budget recommendations based on triangulation data.

    This synthesizes:
    - Signal triangulation (are outcomes following spend?)
    - Efficiency metrics (MER, NCAC headroom)
    - Channel correlation (which platform is working better?)
    - Campaign performance (which specific campaigns to adjust?)

    Returns specific dollar-amount recommendations.
    """
    # Get recently actioned items to filter out
    actioned_items = get_recently_actioned_items(days=3)  # Last 3 days

    # Get all the data we need
    correlation = get_spend_outcome_correlation(days)
    if "error" in correlation:
        return {"error": correlation["error"], "recommendations": []}

    channel_corr = get_channel_correlation(days)
    if "error" in channel_corr:
        channel_corr = {"channels": {"google": {}, "meta": {}}}

    # Get campaign data for the timeframe
    google_camps = get_google_campaigns_for_timeframe(days)
    meta_camps = get_meta_campaigns_for_timeframe(days)

    recommendations = []

    # Define efficiency thresholds
    NCAC_TARGET = 30.0  # Target max NCAC
    MER_FLOOR = 3.0     # Minimum acceptable MER

    current_ncac = correlation["efficiency"]["current_ncac"]
    current_mer = correlation["efficiency"]["current_mer"]
    signal_agreement = correlation["signal_summary"]["agree"]
    spend_direction = correlation["spend_direction"]

    # Calculate headroom
    ncac_headroom = NCAC_TARGET - current_ncac  # Positive = room to grow
    mer_headroom = current_mer - MER_FLOOR      # Positive = room to grow

    # Channel analysis
    google_data = channel_corr.get("channels", {}).get("google", {})
    meta_data = channel_corr.get("channels", {}).get("meta", {})

    google_spend = google_data.get("current_spend", 0)
    meta_spend = meta_data.get("current_spend", 0)

    # Determine overall strategy based on signals and efficiency
    if signal_agreement >= 3 and ncac_headroom > 5 and mer_headroom > 0.5:
        # Strong signals, good efficiency - aggressive growth
        overall_strategy = "scale"
        strategy_reason = f"Strong signal agreement ({signal_agreement}/4), NCAC has ${ncac_headroom:.0f} headroom"
    elif signal_agreement >= 2 and ncac_headroom > 0 and mer_headroom > 0:
        # Decent signals, acceptable efficiency - moderate growth
        overall_strategy = "grow"
        strategy_reason = f"Good signal agreement ({signal_agreement}/4), efficiency metrics healthy"
    elif signal_agreement <= 1 or ncac_headroom < 0 or mer_headroom < 0:
        # Poor signals or efficiency - hold/reduce
        overall_strategy = "hold"
        if ncac_headroom < 0:
            strategy_reason = f"NCAC (${current_ncac:.0f}) exceeds target (${NCAC_TARGET:.0f})"
        elif mer_headroom < 0:
            strategy_reason = f"MER ({current_mer:.1f}) below floor ({MER_FLOOR})"
        else:
            strategy_reason = f"Weak signal agreement ({signal_agreement}/4) - need more data"
    else:
        overall_strategy = "test"
        strategy_reason = "Mixed signals - run controlled tests"

    # Generate channel-level recommendations
    # Calculate recommended changes based on strategy
    if overall_strategy == "scale":
        pct_change = 0.20  # 20% increase
    elif overall_strategy == "grow":
        pct_change = 0.10  # 10% increase
    elif overall_strategy == "hold":
        pct_change = 0.0   # No change
    else:
        pct_change = 0.05  # 5% test increase

    # Meta recommendation (skip if recently actioned)
    meta_daily = meta_spend / days if days > 0 else 0
    meta_new_daily = meta_daily * (1 + pct_change)
    meta_change_amt = (meta_new_daily - meta_daily) * 7  # Weekly impact

    meta_recently_actioned = "Meta" in actioned_items

    if pct_change > 0 and not meta_recently_actioned:
        recommendations.append({
            "id": "meta_budget",
            "priority": "HIGH" if overall_strategy == "scale" else "MEDIUM",
            "action_type": "BUDGET_INCREASE",
            "channel": "Meta",
            "campaign": "All Campaigns",
            "action": f"Increase Meta budget +{int(pct_change*100)}%",
            "current_daily": round(meta_daily, 2),
            "new_daily": round(meta_new_daily, 2),
            "weekly_impact": round(meta_change_amt, 2),
            "reason": strategy_reason,
        })
    elif pct_change == 0 and meta_daily > 0 and not meta_recently_actioned:
        recommendations.append({
            "id": "meta_budget",
            "priority": "LOW",
            "action_type": "BUDGET_HOLD",
            "channel": "Meta",
            "campaign": "All Campaigns",
            "action": "Hold Meta budget steady",
            "current_daily": round(meta_daily, 2),
            "new_daily": round(meta_daily, 2),
            "weekly_impact": 0,
            "reason": strategy_reason,
        })

    # Google recommendation (skip if recently actioned)
    google_daily = google_spend / days if days > 0 else 0
    google_new_daily = google_daily * (1 + pct_change)
    google_change_amt = (google_new_daily - google_daily) * 7

    google_recently_actioned = "Google" in actioned_items

    if pct_change > 0 and not google_recently_actioned:
        recommendations.append({
            "id": "google_budget",
            "priority": "HIGH" if overall_strategy == "scale" else "MEDIUM",
            "action_type": "BUDGET_INCREASE",
            "channel": "Google",
            "campaign": "All Campaigns",
            "action": f"Increase Google budget +{int(pct_change*100)}%",
            "current_daily": round(google_daily, 2),
            "new_daily": round(google_new_daily, 2),
            "weekly_impact": round(google_change_amt, 2),
            "reason": strategy_reason,
        })
    elif pct_change == 0 and google_daily > 0 and not google_recently_actioned:
        recommendations.append({
            "id": "google_budget",
            "priority": "LOW",
            "action_type": "BUDGET_HOLD",
            "channel": "Google",
            "campaign": "All Campaigns",
            "action": "Hold Google budget steady",
            "current_daily": round(google_daily, 2),
            "new_daily": round(google_daily, 2),
            "weekly_impact": 0,
            "reason": strategy_reason,
        })

    # Find top performing campaigns to specifically call out
    # Sort Meta campaigns by efficiency (ROAS or cost per purchase)
    top_meta = []
    for camp in meta_camps:
        spend = camp.get("spend", 0)
        purchases = camp.get("purchases", 0)
        roas = camp.get("purchase_value", 0) / spend if spend > 0 else 0
        if spend > 50 and roas > 2.0:  # Min spend threshold, good ROAS
            top_meta.append({
                "name": camp.get("name", "Unknown"),
                "spend": spend,
                "roas": roas,
                "purchases": purchases,
            })
    top_meta.sort(key=lambda x: x["roas"], reverse=True)

    # Add specific campaign recommendations for top performers (skip if recently actioned)
    for i, camp in enumerate(top_meta[:2]):  # Top 2 Meta campaigns
        camp_name = camp["name"][:50]
        # Check if this campaign was recently actioned
        camp_actioned = any(camp_name in item or item in camp_name for item in actioned_items)
        if overall_strategy in ["scale", "grow"] and not camp_actioned:
            camp_increase = 0.25 if overall_strategy == "scale" else 0.15
            recommendations.append({
                "id": f"meta_camp_{i}",
                "priority": "HIGH",
                "action_type": "CAMPAIGN_SCALE",
                "channel": "Meta",
                "campaign": camp_name,
                "action": f"Scale campaign +{int(camp_increase*100)}%",
                "current_daily": round(camp["spend"] / days, 2),
                "new_daily": round((camp["spend"] / days) * (1 + camp_increase), 2),
                "weekly_impact": round(camp["spend"] * camp_increase, 2),
                "reason": f"Top performer: {camp['roas']:.1f}x ROAS, {camp['purchases']} purchases",
            })

    # Sort Google campaigns
    top_google = []
    for camp in google_camps:
        spend = camp.get("spend", 0)
        conversions = camp.get("conversions", 0)
        roas = camp.get("conversion_value", 0) / spend if spend > 0 else 0
        if spend > 50 and roas > 2.0:
            top_google.append({
                "name": camp.get("name", "Unknown"),
                "spend": spend,
                "roas": roas,
                "conversions": conversions,
            })
    top_google.sort(key=lambda x: x["roas"], reverse=True)

    for i, camp in enumerate(top_google[:2]):
        camp_name = camp["name"][:50]
        # Check if this campaign was recently actioned
        camp_actioned = any(camp_name in item or item in camp_name for item in actioned_items)
        if overall_strategy in ["scale", "grow"] and not camp_actioned:
            camp_increase = 0.25 if overall_strategy == "scale" else 0.15
            recommendations.append({
                "id": f"google_camp_{i}",
                "priority": "HIGH",
                "action_type": "CAMPAIGN_SCALE",
                "channel": "Google",
                "campaign": camp_name,
                "action": f"Scale campaign +{int(camp_increase*100)}%",
                "current_daily": round(camp["spend"] / days, 2),
                "new_daily": round((camp["spend"] / days) * (1 + camp_increase), 2),
                "weekly_impact": round(camp["spend"] * camp_increase, 2),
                "reason": f"Top performer: {camp['roas']:.1f}x ROAS, {int(camp['conversions'])} conversions",
            })

    return {
        "strategy": {
            "overall": overall_strategy,
            "reason": strategy_reason,
        },
        "efficiency": {
            "current_ncac": current_ncac,
            "ncac_target": NCAC_TARGET,
            "ncac_headroom": round(ncac_headroom, 2),
            "current_mer": current_mer,
            "mer_floor": MER_FLOOR,
            "mer_headroom": round(mer_headroom, 2),
        },
        "signal_summary": correlation["signal_summary"],
        "recommendations": recommendations,
        "period_days": days,
    }


@cached(ttl=CACHE_TTL_COMPUTED)
def get_timeframe_summary(days: int = 30) -> dict:
    """
    Get a comprehensive summary for the specified timeframe.
    This is the main function for short-term analysis.
    """
    historical = get_historical_metrics_for_timeframe(days)
    google_camps = get_google_campaigns_for_timeframe(days)
    meta_camps = get_meta_campaigns_for_timeframe(days)

    # Calculate channel breakdowns
    google_spend = sum(c.get("spend", 0) for c in google_camps)
    google_revenue = sum(c.get("conversion_value", 0) for c in google_camps)
    meta_spend = sum(c.get("spend", 0) for c in meta_camps)
    meta_revenue = sum(c.get("purchase_value", 0) for c in meta_camps)

    # Get comparison period (previous N days)
    prev_historical = get_kendall_historical()
    prev_metrics = []
    if prev_historical:
        all_metrics = prev_historical.get("metrics", [])
        cutoff_current = get_date_cutoff(days)
        cutoff_prev = get_date_cutoff(days * 2)
        prev_metrics = [m for m in all_metrics if cutoff_prev <= m.get("date", "") < cutoff_current]

    prev_sales = sum(m.get("sales", 0) for m in prev_metrics)
    prev_orders = sum(m.get("orders", 0) for m in prev_metrics)
    prev_cam = sum(m.get("contrib_after_mkt", 0) for m in prev_metrics)

    # Calculate changes
    current_sales = historical.get("total_sales", 0)
    current_orders = historical.get("total_orders", 0)
    current_cam = historical.get("total_cam", 0)

    sales_change = ((current_sales - prev_sales) / prev_sales * 100) if prev_sales > 0 else 0
    orders_change = ((current_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else 0
    cam_change = ((current_cam - prev_cam) / prev_cam * 100) if prev_cam > 0 else 0

    # Identify problem campaigns (low ROAS in recent period)
    problem_campaigns = []
    for camp in google_camps + meta_camps:
        if camp.get("spend", 0) > 50 and camp.get("roas", 0) < 1.5:
            problem_campaigns.append({
                "name": camp["name"],
                "channel": "Google" if camp in google_camps else "Meta",
                "spend": camp["spend"],
                "roas": camp["roas"],
                "days_active": camp.get("days_active", 0),
            })

    problem_campaigns.sort(key=lambda x: x["spend"], reverse=True)

    # Identify winning campaigns
    winning_campaigns = []
    for camp in google_camps + meta_camps:
        if camp.get("spend", 0) > 30 and camp.get("roas", 0) >= 3.0:
            winning_campaigns.append({
                "name": camp["name"],
                "channel": "Google" if camp in google_camps else "Meta",
                "spend": camp["spend"],
                "roas": camp["roas"],
                "revenue": camp.get("conversion_value", camp.get("purchase_value", 0)),
            })

    winning_campaigns.sort(key=lambda x: x["roas"], reverse=True)

    now_est = datetime.now(EST)
    # Data is pulled at 8 AM, so "yesterday" means the previous complete day
    # The most recent complete data is from 2 days ago through yesterday
    yesterday = now_est - timedelta(days=1)
    start_date = (now_est - timedelta(days=days)).strftime("%b %d")
    end_date = yesterday.strftime("%b %d")

    if days == 1:
        label = f"Yesterday ({end_date})"
    else:
        label = f"Last {days} days ({start_date} - {end_date})"

    return {
        "timeframe": {
            "days": days,
            "label": label,
            "note": "Data as of 8:00 AM EST pull",
        },
        "summary": {
            "total_sales": current_sales,
            "total_orders": current_orders,
            "total_spend": historical.get("total_spend", 0),
            "total_cam": current_cam,
            "cam_per_order": historical.get("cam_per_order", 0),
            "avg_ncac": historical.get("avg_ncac", 0),
            "blended_roas": historical.get("blended_roas", 0),
        },
        "changes": {
            "sales_change_pct": sales_change,
            "orders_change_pct": orders_change,
            "cam_change_pct": cam_change,
            "comparison_period": f"vs previous {days} days",
        },
        "channels": {
            "google": {
                "spend": google_spend,
                "revenue": google_revenue,
                "roas": google_revenue / google_spend if google_spend > 0 else 0,
                "campaigns": len(google_camps),
            },
            "meta": {
                "spend": meta_spend,
                "revenue": meta_revenue,
                "roas": meta_revenue / meta_spend if meta_spend > 0 else 0,
                "campaigns": len(meta_camps),
            },
            "amazon": {
                "sales": historical.get("amazon_sales", 0),
                "orders": historical.get("amazon_orders", 0),
                "spend": historical.get("amazon_spend", 0),
                "roas": historical.get("amazon_roas", 0),
                "meta_first_click": historical.get("meta_first_click", 0),
                "data_source": historical.get("amazon_data_source", "unknown"),
            },
        },
        "problem_campaigns": problem_campaigns[:10],
        "winning_campaigns": winning_campaigns[:10],
        "google_campaigns": google_camps,
        "meta_campaigns": meta_camps,
        "daily_metrics": historical.get("daily_metrics", []),
    }
