"""
TOF Analysis - Top of Funnel effectiveness measurement.

Uses branded search as a proxy to measure whether TOF is creating demand.
"""

import streamlit as st
import pandas as pd

from data_loader import (
    get_latest_report,
    get_gsc_branded,
    get_gsc_daily_trend,
    get_kendall_attribution,
    format_currency,
    format_percent,
)


def render():
    st.title("TOF Analysis")
    st.markdown("*Is Top-of-Funnel creating demand? Branded search tells us.*")

    # Key concept explanation
    with st.expander("Why Branded Search Matters", expanded=False):
        st.markdown("""
        **The Problem with TOF ROAS:**
        - Meta TOF might show 1.3x ROAS (looks bad)
        - But those people Google "TuffWraps" later
        - Google branded search gets the conversion credit
        - Meta looks bad, Google looks like a hero

        **How to Measure TOF's True Impact:**
        1. When TOF spend goes up → branded search should increase in 7-14 days
        2. When TOF spend goes down → branded search should decrease
        3. If no correlation → TOF might not be reaching new people
        """)

    st.markdown("---")

    # Branded vs Non-Branded summary
    gsc_data = get_gsc_branded()
    report = get_latest_report()

    if not gsc_data:
        st.error("No Google Search Console data available.")
        return

    # Top metrics
    st.subheader("Branded Search Overview (30 days)")

    col1, col2, col3, col4 = st.columns(4)

    branded = gsc_data.get("branded", {})
    non_branded = gsc_data.get("non_branded", {})

    with col1:
        st.metric(
            "Branded Clicks",
            f"{branded.get('clicks', 0):,}",
            help="Searches containing 'tuffwraps', 'tuff wraps', etc."
        )

    with col2:
        st.metric(
            "Branded CTR",
            format_percent(branded.get("ctr", 0) * 100),
            help="Click-through rate for branded searches"
        )

    with col3:
        branded_pct = gsc_data.get("branded_percentage", 0)
        st.metric(
            "Branded % of Total",
            format_percent(branded_pct),
            help="What portion of all search clicks are branded"
        )

    with col4:
        total_clicks = gsc_data.get("total_clicks", 0)
        st.metric("Total Search Clicks", f"{total_clicks:,}")

    st.markdown("---")

    # Daily branded search trend
    st.subheader("Daily Branded Search Trend")

    daily_trend = get_gsc_daily_trend()

    if daily_trend:
        trend_df = pd.DataFrame(daily_trend)
        trend_df["date"] = pd.to_datetime(trend_df["date"])
        trend_df = trend_df.sort_values("date")

        # Chart with branded clicks
        st.line_chart(
            trend_df.set_index("date")[["branded_clicks", "non_branded_clicks"]],
            use_container_width=True,
        )

        # Rolling average
        trend_df["branded_7d_avg"] = trend_df["branded_clicks"].rolling(7).mean()

        st.markdown("**7-Day Rolling Average**")
        st.line_chart(
            trend_df.set_index("date")["branded_7d_avg"],
            use_container_width=True,
        )

        # Trend analysis
        recent_7d = trend_df.tail(7)["branded_clicks"].mean()
        prior_7d = trend_df.tail(14).head(7)["branded_clicks"].mean()

        if prior_7d > 0:
            change = ((recent_7d - prior_7d) / prior_7d) * 100

            if change > 5:
                st.success(f"Branded search UP {change:.1f}% week-over-week. TOF is likely creating demand.")
            elif change < -5:
                st.warning(f"Branded search DOWN {change:.1f}% week-over-week. Monitor TOF performance.")
            else:
                st.info(f"Branded search stable ({change:+.1f}% WoW). Demand generation is steady.")

    st.markdown("---")

    # TOF Campaign breakdown
    st.subheader("TOF Campaign Performance")

    attribution = get_kendall_attribution()

    if attribution:
        # Get Meta TOF campaigns
        meta_data = attribution.get("Meta Ads", {}).get("breakdowns", {})

        tof_campaigns = []
        for name, metrics in meta_data.items():
            if "tof" in name.lower() or "prospecting" in name.lower():
                tof_campaigns.append({
                    "Campaign": name,
                    "Orders": metrics.get("orders", 0),
                    "Revenue": metrics.get("sales", 0),
                    "NC Orders": metrics.get("nc_orders", 0),
                    "NC %": metrics.get("nc_pct", 0) * 100,
                    "ROAS": metrics.get("roas", 0),
                    "NC ROAS": metrics.get("nc_roas", 0),
                })

        if tof_campaigns:
            tof_df = pd.DataFrame(tof_campaigns)

            st.markdown("**Meta TOF/Prospecting Campaigns**")
            st.dataframe(
                tof_df.style.format({
                    "Revenue": "${:,.0f}",
                    "NC %": "{:.0f}%",
                    "ROAS": "{:.2f}x",
                    "NC ROAS": "{:.2f}x",
                }),
                use_container_width=True,
                hide_index=True,
            )

            # TOF Summary
            total_tof_orders = sum(c["Orders"] for c in tof_campaigns)
            total_tof_revenue = sum(c["Revenue"] for c in tof_campaigns)
            total_nc_orders = sum(c["NC Orders"] for c in tof_campaigns)

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total TOF Orders", f"{total_tof_orders:,}")
            with col2:
                st.metric("TOF Revenue (Kendall)", format_currency(total_tof_revenue))
            with col3:
                nc_pct = (total_nc_orders / total_tof_orders * 100) if total_tof_orders > 0 else 0
                st.metric("TOF New Customer %", format_percent(nc_pct))

    st.markdown("---")

    # Top branded search queries
    st.subheader("Top Branded Search Queries")

    branded_queries = branded.get("queries", [])

    if branded_queries:
        queries_df = pd.DataFrame(branded_queries[:15])
        queries_df = queries_df.rename(columns={
            "query": "Query",
            "clicks": "Clicks",
            "impressions": "Impressions",
            "ctr": "CTR",
            "position": "Avg Position"
        })

        st.dataframe(
            queries_df.style.format({
                "CTR": "{:.1%}",
                "Avg Position": "{:.1f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")

    # Interpretation guidance
    st.subheader("How to Interpret")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Healthy TOF Signals:**
        - Branded search trending up
        - 15-25% of total clicks are branded
        - High new customer % on TOF campaigns
        - Branded CTR > 40%
        """)

    with col2:
        st.markdown("""
        **Warning Signs:**
        - Branded search flat or declining
        - < 15% branded clicks
        - TOF campaigns mostly hitting existing customers
        - Branded searches not converting
        """)

    # TOF recommendation
    st.markdown("---")
    branded_pct = gsc_data.get("branded_percentage", 0)

    if branded_pct >= 20:
        st.success(f"""
        **TOF Assessment: Likely Working**

        Branded search is {branded_pct:.1f}% of total clicks.
        This suggests good brand awareness. Monitor the trend over time.
        """)
    elif branded_pct >= 15:
        st.info(f"""
        **TOF Assessment: Moderate**

        Branded search is {branded_pct:.1f}% of total clicks.
        Consider testing increased TOF spend and monitor branded search response.
        """)
    else:
        st.warning(f"""
        **TOF Assessment: Needs Attention**

        Branded search is only {branded_pct:.1f}% of total clicks.
        TOF may not be creating enough brand awareness.
        Consider creative refresh or audience expansion.
        """)
