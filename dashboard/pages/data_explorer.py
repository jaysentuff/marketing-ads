"""
Data Explorer - Raw data view and debugging.

Allows exploration of the underlying JSON data files.
"""

import streamlit as st
import json
import pandas as pd

from data_loader import (
    get_latest_report,
    get_kendall_attribution,
    get_kendall_pnl,
    get_gsc_branded,
    get_gsc_daily_trend,
    get_shopify_metrics,
    get_google_ads_campaigns,
    get_meta_ads_campaigns,
    get_ga4_summary,
    get_klaviyo_summary,
)


def render():
    st.title("Data Explorer")
    st.markdown("*View raw data from all sources*")

    data_source = st.selectbox(
        "Select Data Source",
        [
            "CAM Report (Aggregated)",
            "Kendall Attribution",
            "Kendall P&L",
            "Google Search Console",
            "GSC Daily Trend",
            "Shopify Metrics",
            "Google Ads Campaigns",
            "Meta Ads Campaigns",
            "GA4 Summary",
            "Klaviyo Summary",
        ]
    )

    st.markdown("---")

    data = None

    if data_source == "CAM Report (Aggregated)":
        data = get_latest_report()
    elif data_source == "Kendall Attribution":
        data = get_kendall_attribution()
    elif data_source == "Kendall P&L":
        data = get_kendall_pnl()
    elif data_source == "Google Search Console":
        data = get_gsc_branded()
    elif data_source == "GSC Daily Trend":
        data = get_gsc_daily_trend()
    elif data_source == "Shopify Metrics":
        data = get_shopify_metrics()
    elif data_source == "Google Ads Campaigns":
        data = get_google_ads_campaigns()
    elif data_source == "Meta Ads Campaigns":
        data = get_meta_ads_campaigns()
    elif data_source == "GA4 Summary":
        data = get_ga4_summary()
    elif data_source == "Klaviyo Summary":
        data = get_klaviyo_summary()

    if data is None:
        st.warning("No data available for this source. Run the daily data pull first.")
        st.code("cd E:/VS Code/Marketing Ads/connectors && python pull_all_data.py")
        return

    # Show data type info
    if isinstance(data, list):
        st.info(f"Data type: List with {len(data)} items")
    elif isinstance(data, dict):
        st.info(f"Data type: Dictionary with {len(data)} keys")

    # Display options
    view_mode = st.radio("View Mode", ["Pretty JSON", "Table (if applicable)", "Raw"], horizontal=True)

    if view_mode == "Pretty JSON":
        st.json(data)

    elif view_mode == "Table (if applicable)":
        try:
            if isinstance(data, list):
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
            elif isinstance(data, dict):
                # Try to find a list within the dict
                found_list = False
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        st.subheader(f"Table: {key}")
                        df = pd.DataFrame(value)
                        st.dataframe(df, use_container_width=True)
                        found_list = True

                if not found_list:
                    # Show dict as table
                    flat_data = []
                    for key, value in data.items():
                        if isinstance(value, dict):
                            for k2, v2 in value.items():
                                flat_data.append({"Key": f"{key}.{k2}", "Value": str(v2)})
                        else:
                            flat_data.append({"Key": key, "Value": str(value)})
                    df = pd.DataFrame(flat_data)
                    st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Could not convert to table: {e}")
            st.json(data)

    else:  # Raw
        st.code(json.dumps(data, indent=2, default=str), language="json")

    # Data file info
    st.markdown("---")
    st.subheader("Data Files Location")
    st.code("E:/VS Code/Marketing Ads/connectors/data/")

    st.markdown("""
    **File Structure:**
    - `aggregated/` - Combined CAM reports
    - `kendall/` - Kendall.ai attribution data
    - `gsc/` - Google Search Console data
    - `shopify/` - Shopify orders and metrics
    - `google_ads/` - Google Ads campaign data
    - `meta_ads/` - Meta Ads campaign data
    - `ga4/` - Google Analytics 4 data
    - `klaviyo/` - Klaviyo email/SMS data
    """)
