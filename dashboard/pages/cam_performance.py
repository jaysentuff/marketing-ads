"""
CAM Performance - Detailed channel and campaign analysis.
"""

import streamlit as st
import pandas as pd

from data_loader import (
    get_latest_report,
    get_kendall_attribution,
    get_channel_campaigns,
    format_currency,
    format_percent,
)


def render():
    st.title("CAM Performance")
    st.markdown("*Contribution After Marketing by channel and campaign*")

    report = get_latest_report()
    if not report:
        st.error("No data available.")
        return

    r = report.get("report", {})
    summary = r.get("summary", {})
    channels = r.get("channels", {})

    # Summary metrics
    st.subheader("30-Day Summary")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Revenue", format_currency(summary.get("total_revenue", 0)))
    with col2:
        st.metric("COGS", format_currency(summary.get("total_cogs", 0)))
    with col3:
        st.metric("Shipping", format_currency(summary.get("total_shipping", 0)))
    with col4:
        st.metric("Ad Spend", format_currency(summary.get("total_ad_spend", 0)))
    with col5:
        st.metric("Blended CAM", format_currency(summary.get("blended_cam", 0)))

    st.markdown("---")

    # CAM by Channel bar chart
    st.subheader("CAM by Channel")

    channel_df = pd.DataFrame([
        {
            "Channel": name,
            "CAM": data.get("cam", 0),
            "Revenue": data.get("revenue", 0),
            "Orders": data.get("orders", 0),
            "Ad Spend": data.get("ad_spend", 0),
            "ROAS": data.get("roas", 0),
            "NC ROAS": data.get("nc_roas", 0),
        }
        for name, data in [
            ("Google Ads", channels.get("google_ads", {})),
            ("Meta Ads", channels.get("meta_ads", {})),
            ("Organic", channels.get("organic", {})),
            ("Klaviyo", channels.get("klaviyo", {})),
        ]
    ])

    # Bar chart of CAM
    st.bar_chart(channel_df.set_index("Channel")["CAM"])

    # Detailed table
    st.dataframe(
        channel_df.style.format({
            "CAM": "${:,.0f}",
            "Revenue": "${:,.0f}",
            "Ad Spend": "${:,.0f}",
            "ROAS": "{:.2f}x",
            "NC ROAS": "{:.2f}x",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # Channel drill-down
    st.subheader("Campaign Breakdown")

    channel = st.selectbox(
        "Select Channel",
        ["Google Ads", "Meta Ads", "Klaviyo", "Organic"]
    )

    campaigns = get_channel_campaigns(channel)

    if campaigns:
        campaign_df = pd.DataFrame(campaigns)
        campaign_df = campaign_df.rename(columns={
            "name": "Campaign",
            "orders": "Orders",
            "revenue": "Revenue",
            "nc_orders": "New Cust",
            "nc_revenue": "NC Revenue",
            "nc_pct": "NC %",
            "roas": "ROAS",
            "nc_roas": "NC ROAS",
        })

        # Filter to campaigns with orders
        campaign_df = campaign_df[campaign_df["Orders"] > 0]

        st.dataframe(
            campaign_df.style.format({
                "Revenue": "${:,.0f}",
                "NC Revenue": "${:,.0f}",
                "NC %": "{:.0%}",
                "ROAS": "{:.2f}x",
                "NC ROAS": "{:.2f}x",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No campaign data available for this channel.")

    st.markdown("---")

    # New vs Returning breakdown
    st.subheader("New vs Returning Customers")

    nc_data = []
    for name, data in channels.items():
        nc_orders = data.get("new_customer_orders", 0)
        rc_orders = data.get("returning_customer_orders", 0)
        total = nc_orders + rc_orders
        if total > 0:
            nc_data.append({
                "Channel": data.get("name", name),
                "New Customers": nc_orders,
                "Returning Customers": rc_orders,
                "Total Orders": total,
                "NC %": nc_orders / total * 100,
            })

    if nc_data:
        nc_df = pd.DataFrame(nc_data)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Order Distribution**")
            chart_data = nc_df.set_index("Channel")[["New Customers", "Returning Customers"]]
            st.bar_chart(chart_data)

        with col2:
            st.markdown("**New Customer %**")
            st.dataframe(
                nc_df[["Channel", "New Customers", "Returning Customers", "NC %"]].style.format({
                    "NC %": "{:.1f}%"
                }),
                use_container_width=True,
                hide_index=True,
            )

    # CAM per order comparison
    st.markdown("---")
    st.subheader("CAM per Order by Channel")

    cam_per_order_data = []
    for name, data in [
        ("Google Ads", channels.get("google_ads", {})),
        ("Meta Ads", channels.get("meta_ads", {})),
        ("Organic", channels.get("organic", {})),
        ("Klaviyo", channels.get("klaviyo", {})),
    ]:
        orders = data.get("orders", 0)
        cam = data.get("cam", 0)
        if orders > 0:
            cam_per_order_data.append({
                "Channel": name,
                "CAM per Order": cam / orders,
                "Orders": orders,
            })

    if cam_per_order_data:
        cpo_df = pd.DataFrame(cam_per_order_data)
        st.bar_chart(cpo_df.set_index("Channel")["CAM per Order"])

        st.caption("Higher CAM per order = more profitable channel")
