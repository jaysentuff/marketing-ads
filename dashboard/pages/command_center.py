"""
Command Center - Daily Decision Dashboard

The home page showing what to do today based on CAM analysis.

IMPORTANT: TOF (Top-of-Funnel) campaigns are evaluated differently:
- NOT by direct ROAS (which will look bad for TOF)
- BY: First-click attribution, branded search correlation, blended NCAC
"""

import streamlit as st

from data_loader import (
    get_latest_report,
    get_decision_signals,
    get_blended_metrics,
    format_currency,
    format_percent,
)


def get_health_status(cam_per_order: float, target: float = 20) -> tuple[str, str, str]:
    """Return (status, color, emoji) based on CAM health."""
    if cam_per_order >= target * 1.2:
        return "EXCELLENT", "#00c853", "🟢"
    elif cam_per_order >= target:
        return "HEALTHY", "#4caf50", "🟢"
    elif cam_per_order >= target * 0.8:
        return "CAUTION", "#ff9800", "🟡"
    else:
        return "CRITICAL", "#f44336", "🔴"


def render():
    st.title("📊 Command Center")

    report = get_latest_report()

    if not report:
        st.error("No data available. Run the daily data pull first.")
        st.code("python E:/VS Code/Marketing Ads/connectors/pull_all_data.py")
        return

    r = report.get("report", {})
    summary = r.get("summary", {})
    channels = r.get("channels", {})
    signals = get_decision_signals()

    # Calculate health status
    cam_per_order = summary.get("blended_cam_per_order", 0)
    target = 20
    status, color, emoji = get_health_status(cam_per_order, target)

    # Hero Section - Overall Health
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}22, {color}11);
                border-left: 4px solid {color};
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;">
        <h2 style="margin: 0; color: {color};">{emoji} Overall Status: {status}</h2>
        <p style="margin: 10px 0 0 0; font-size: 1.1em;">
            CAM per Order: <strong>${cam_per_order:.2f}</strong> (Target: $20)
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Quick Action Card
    spend = signals["spend_decision"]
    if spend == "increase":
        action_color = "#00c853"
        action_emoji = "📈"
        action_text = "SCALE SPEND"
        action_detail = "CAM is healthy. Consider increasing ad spend by 10-15%."
    elif spend == "decrease":
        action_color = "#f44336"
        action_emoji = "📉"
        action_text = "CUT SPEND"
        action_detail = "CAM is below target. Reduce spend on worst performers."
    else:
        action_color = "#2196f3"
        action_emoji = "⏸️"
        action_text = "HOLD SPEND"
        action_detail = "CAM is stable. Maintain current spend levels."

    st.markdown(f"""
    <div style="background: {action_color}15;
                border: 2px solid {action_color};
                padding: 15px 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: center;">
        <span style="font-size: 2em;">{action_emoji}</span>
        <h3 style="margin: 5px 0; color: {action_color};">TODAY'S ACTION: {action_text}</h3>
        <p style="margin: 0;">{action_detail}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Key Metrics in clean cards
    st.subheader("📈 Key Metrics (Last 30 Days)")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cam = summary.get("blended_cam", 0)
        st.metric(
            label="Total CAM",
            value=format_currency(cam),
            help="Contribution After Marketing = Revenue - COGS - Shipping - Ad Spend"
        )

    with col2:
        delta = cam_per_order - target
        st.metric(
            label="CAM per Order",
            value=format_currency(cam_per_order),
            delta=f"{delta:+.2f} vs $20 target",
            delta_color="normal" if delta >= 0 else "inverse",
        )

    with col3:
        total_orders = summary.get("total_orders", 0)
        st.metric(
            label="Total Orders",
            value=f"{total_orders:,}",
        )

    with col4:
        ad_spend = summary.get("total_ad_spend", 0)
        st.metric(
            label="Ad Spend",
            value=format_currency(ad_spend),
        )

    st.markdown("---")

    # Decision signals
    signals = get_decision_signals()

    # Main decision cards
    st.subheader("Today's Decisions")

    col1, col2 = st.columns(2)

    with col1:
        # Spend decision
        spend = signals["spend_decision"]
        if spend == "increase":
            st.success("**SCALE SPEND**")
            st.markdown("CAM is healthy. Consider increasing total ad spend by 10-15%.")
        elif spend == "decrease":
            st.error("**CUT SPEND**")
            st.markdown("CAM is below target. Cut spend on worst performers until CAM recovers.")
        else:
            st.info("**HOLD SPEND**")
            st.markdown("CAM is stable. Maintain current spend levels.")

    with col2:
        # Channel shift
        shift = signals["channel_shift"]
        if shift:
            st.warning("**SHIFT BUDGET**")
            st.markdown(f"Consider shifting 10-20% from **{shift['from']}** to **{shift['to']}**")
            st.markdown(f"*{shift['reason']}*")
        else:
            st.info("**CHANNELS BALANCED**")
            st.markdown("No significant channel shift recommended.")

    st.markdown("---")

    # Channel CAM breakdown
    st.subheader("Channel Performance (Kendall Attribution)")

    channel_cols = st.columns(4)

    channel_data = [
        ("Google Ads", channels.get("google_ads", {})),
        ("Meta Ads", channels.get("meta_ads", {})),
        ("Organic", channels.get("organic", {})),
        ("Klaviyo", channels.get("klaviyo", {})),
    ]

    for col, (name, data) in zip(channel_cols, channel_data):
        with col:
            cam = data.get("cam", 0)
            orders = data.get("orders", 0)
            roas = data.get("roas", 0)
            nc_pct = (data.get("new_customer_orders", 0) / orders * 100) if orders > 0 else 0

            st.markdown(f"**{name}**")
            st.metric("CAM", format_currency(cam))
            st.caption(f"{orders:,} orders | {roas:.2f}x ROAS | {nc_pct:.0f}% new")

    st.markdown("---")

    # Alerts
    if signals["alerts"]:
        st.subheader("Alerts")
        for alert in signals["alerts"]:
            st.warning(alert)

    # TOF Assessment - Critical section
    tof = signals.get("tof_assessment")
    if tof:
        st.subheader("TOF (Top-of-Funnel) Assessment")

        st.info("""
        **Why TOF is measured differently:**
        TOF campaigns show low direct ROAS because customers don't buy immediately.
        They see your ad, then Google your brand later. We measure TOF by:
        first-click attribution, branded search, and blended new customer metrics.
        """)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Meta First-Click (7d)",
                format_currency(tof.get("meta_first_click_7d", 0)),
                delta=f"{tof.get('meta_fc_trend', 0):+.1f}% WoW" if tof.get("meta_fc_trend") else None,
            )

        with col2:
            ncac = tof.get("ncac_7d_avg", 0)
            st.metric(
                "Blended NCAC",
                format_currency(ncac) if ncac else "N/A",
                delta="Below $50 target" if ncac and ncac < 50 else "Above $50 target" if ncac else None,
                delta_color="normal" if ncac and ncac < 50 else "inverse",
            )

        with col3:
            st.metric(
                "Branded Search %",
                format_percent(tof.get("branded_search_pct", 0)),
                help="Higher = more brand awareness from TOF"
            )

        with col4:
            st.metric(
                "Amazon Sales (7d)",
                format_currency(tof.get("amazon_sales_7d", 0)),
                delta=f"{tof.get('amazon_trend', 0):+.1f}% WoW" if tof.get("amazon_trend") else None,
            )

        # TOF verdict
        verdict = tof.get("verdict", "")
        message = tof.get("message", "")

        if verdict == "healthy":
            st.success(f"**TOF Status: HEALTHY** - {message}")
        elif verdict == "working":
            st.info(f"**TOF Status: WORKING** - {message}")
        else:
            st.warning(f"**TOF Status: REVIEW NEEDED** - {message}")

        # Show TOF campaigns
        tof_campaigns = tof.get("campaigns", [])
        if tof_campaigns:
            with st.expander("TOF Campaign Details", expanded=False):
                for c in tof_campaigns:
                    st.markdown(
                        f"- **{c['name'][:50]}** ({c['channel']}) - "
                        f"{c['orders']} orders, {c.get('nc_pct', 0)*100:.0f}% new customers"
                    )
                st.caption("Note: Direct ROAS not shown for TOF - it's not the right metric")

    st.markdown("---")

    # Direct Response Campaign Actions
    st.subheader("Direct Response Campaigns")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Scale (ROAS 3.0+)**")
        scale_campaigns = signals["campaigns_to_scale"][:5]
        if scale_campaigns:
            for c in scale_campaigns:
                nc_pct = c.get('nc_pct', 0) * 100
                st.markdown(
                    f"- **{c['name'][:40]}...** ({c['channel']}) - {c['roas']:.2f}x ROAS, {nc_pct:.0f}% new"
                )
        else:
            st.caption("No campaigns meeting scale criteria")

    with col2:
        st.markdown("**Watch List (needs review)**")
        watch_campaigns = signals.get("campaigns_to_watch", [])[:5]
        if watch_campaigns:
            for c in watch_campaigns:
                st.markdown(
                    f"- **{c['name'][:40]}...** ({c['channel']}) - {c['roas']:.2f}x ROAS"
                )
                st.caption(f"   {c.get('note', '')}")
        else:
            st.caption("No campaigns flagged for review")

    st.markdown("---")

    # Attribution gap warning
    platform_vs_kendall = r.get("platform_vs_kendall", {})
    over_attr = platform_vs_kendall.get("over_attribution_pct", 0)

    st.subheader("Platform Attribution Gap")

    col1, col2, col3 = st.columns(3)

    with col1:
        platform_total = platform_vs_kendall.get("platform_total", 0)
        st.metric("Platform Claimed Revenue", format_currency(platform_total))

    with col2:
        kendall_total = platform_vs_kendall.get("kendall_total", 0)
        st.metric("Kendall Attributed Revenue", format_currency(kendall_total))

    with col3:
        st.metric(
            "Over-Attribution",
            format_percent(over_attr),
            delta=None,
            help="How much platforms over-claim compared to de-duplicated Kendall attribution"
        )

    if over_attr > 30:
        st.warning(
            f"Platforms are over-claiming by {over_attr:.0f}%. "
            "Use Kendall attribution for decisions, not platform-reported ROAS."
        )

    # Generated time
    generated_at = report.get("generated_at", "Unknown")
    st.caption(f"Report generated: {generated_at}")
