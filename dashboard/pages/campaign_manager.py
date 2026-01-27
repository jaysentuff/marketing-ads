"""
Campaign Manager - Campaign-level performance and recommendations.

Shows which campaigns to scale, hold, or cut based on CAM.
"""

import streamlit as st
import pandas as pd

from data_loader import (
    get_latest_report,
    get_kendall_attribution,
    get_google_ads_campaigns,
    get_meta_ads_campaigns,
    format_currency,
    format_percent,
)


def get_recommendation(roas: float, orders: int) -> tuple[str, str]:
    """
    Get campaign recommendation based on ROAS and order volume.

    Returns (recommendation, color) tuple.
    """
    if orders < 5:
        return "Low Volume", "gray"

    if roas >= 3.0:
        return "SCALE", "green"
    elif roas >= 2.0:
        return "HOLD", "orange"
    elif roas >= 1.5:
        return "WATCH", "yellow"
    else:
        return "CUT", "red"


def render():
    st.title("Campaign Manager")
    st.markdown("*Scale, hold, or cut based on Kendall attribution*")

    # Decision framework reference
    with st.expander("Decision Framework", expanded=False):
        st.markdown("""
        | ROAS (Kendall) | Orders | Action |
        |----------------|--------|--------|
        | 3.0+ | 10+ | **SCALE** - Increase budget 20% |
        | 2.0-3.0 | 10+ | **HOLD** - Maintain current spend |
        | 1.5-2.0 | 10+ | **WATCH** - Monitor for 5 more days |
        | < 1.5 | 20+ | **CUT** - Pause or cut budget 50% |
        | Any | < 5 | **Low Volume** - Need more data |

        *Based on Kendall de-duplicated attribution, not platform ROAS*
        """)

    st.markdown("---")

    attribution = get_kendall_attribution()

    if not attribution:
        st.error("No Kendall attribution data available.")
        return

    # Channel tabs
    tab1, tab2, tab3 = st.tabs(["Google Ads", "Meta Ads", "Klaviyo"])

    with tab1:
        render_channel_campaigns("Google Ads", attribution)

    with tab2:
        render_channel_campaigns("Meta Ads", attribution)

    with tab3:
        render_channel_campaigns("Klaviyo", attribution)

    st.markdown("---")

    # Summary action list
    st.subheader("Action Summary")

    all_campaigns = []

    for channel in ["Google Ads", "Meta Ads"]:
        channel_data = attribution.get(channel, {})
        breakdowns = channel_data.get("breakdowns", {})

        for name, metrics in breakdowns.items():
            orders = metrics.get("orders", 0)
            roas = metrics.get("roas", 0)

            if orders >= 5:  # Only include campaigns with meaningful volume
                rec, color = get_recommendation(roas, orders)
                all_campaigns.append({
                    "Channel": channel,
                    "Campaign": name,
                    "Orders": orders,
                    "Revenue": metrics.get("sales", 0),
                    "ROAS": roas,
                    "NC ROAS": metrics.get("nc_roas", 0),
                    "NC %": metrics.get("nc_pct", 0) * 100,
                    "Action": rec,
                })

    if all_campaigns:
        # Group by action
        scale_campaigns = [c for c in all_campaigns if c["Action"] == "SCALE"]
        cut_campaigns = [c for c in all_campaigns if c["Action"] == "CUT"]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Campaigns to Scale** (ROAS 3.0+)")
            if scale_campaigns:
                for c in sorted(scale_campaigns, key=lambda x: x["ROAS"], reverse=True)[:5]:
                    st.success(f"**{c['Campaign'][:45]}**")
                    st.caption(f"{c['Channel']} | {c['ROAS']:.2f}x ROAS | {c['Orders']} orders | ${c['Revenue']:,.0f}")
            else:
                st.info("No campaigns meeting scale criteria")

        with col2:
            st.markdown("**Campaigns to Cut** (ROAS < 1.5, 20+ orders)")
            if cut_campaigns:
                for c in sorted(cut_campaigns, key=lambda x: x["ROAS"])[:5]:
                    st.error(f"**{c['Campaign'][:45]}**")
                    st.caption(f"{c['Channel']} | {c['ROAS']:.2f}x ROAS | {c['Orders']} orders | ${c['Revenue']:,.0f}")
            else:
                st.info("No campaigns meeting cut criteria")


def render_channel_campaigns(channel: str, attribution: dict):
    """Render campaign table for a specific channel."""
    channel_data = attribution.get(channel, {})
    breakdowns = channel_data.get("breakdowns", {})
    total = channel_data.get("total", {})

    # Channel summary
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Orders", f"{total.get('orders', 0):,}")
    with col2:
        st.metric("Total Revenue", format_currency(total.get("sales", 0)))
    with col3:
        st.metric("Blended ROAS", f"{total.get('roas', 0):.2f}x")
    with col4:
        st.metric("NC ROAS", f"{total.get('nc_roas', 0):.2f}x")

    # Build campaign dataframe
    campaigns = []

    for name, metrics in breakdowns.items():
        orders = metrics.get("orders", 0)
        roas = metrics.get("roas", 0)
        rec, _ = get_recommendation(roas, orders)

        campaigns.append({
            "Campaign": name,
            "Orders": orders,
            "Revenue": metrics.get("sales", 0),
            "NC Orders": metrics.get("nc_orders", 0),
            "NC %": metrics.get("nc_pct", 0) * 100 if metrics.get("nc_pct") else 0,
            "ROAS": roas,
            "NC ROAS": metrics.get("nc_roas", 0),
            "Action": rec,
        })

    if campaigns:
        df = pd.DataFrame(campaigns)

        # Sort by orders descending
        df = df.sort_values("Orders", ascending=False)

        # Filter to campaigns with orders
        df = df[df["Orders"] > 0]

        # Color code the Action column
        def highlight_action(val):
            if val == "SCALE":
                return "background-color: #10B98133"
            elif val == "CUT":
                return "background-color: #EF444433"
            elif val == "WATCH":
                return "background-color: #F59E0B33"
            return ""

        st.dataframe(
            df.style
            .format({
                "Revenue": "${:,.0f}",
                "NC %": "{:.0f}%",
                "ROAS": "{:.2f}x",
                "NC ROAS": "{:.2f}x",
            })
            .applymap(highlight_action, subset=["Action"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(f"No campaign data for {channel}")
