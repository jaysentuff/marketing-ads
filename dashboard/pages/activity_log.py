"""
Activity Log - Track marketing decisions and changes.

Log what you've done so the AI can reference it later.
"""

import streamlit as st
from datetime import datetime

from changelog import (
    load_changelog,
    add_entry,
    get_recent_entries,
    delete_entry,
    ACTION_TYPES,
)
from data_loader import get_latest_report, format_currency


def render():
    st.title("Activity Log")
    st.markdown("Track your marketing decisions so the AI can learn from your history")

    # Get current metrics for snapshot
    report = get_latest_report()
    current_metrics = {}
    if report:
        r = report.get("report", {})
        summary = r.get("summary", {})
        current_metrics = {
            "cam_per_order": summary.get("blended_cam_per_order", 0),
            "total_orders": summary.get("total_orders", 0),
            "ad_spend": summary.get("total_ad_spend", 0),
        }

    # Add new entry form
    st.subheader("Log New Action")

    with st.form("new_entry"):
        col1, col2 = st.columns(2)

        with col1:
            action_type = st.selectbox(
                "Action Type",
                options=[a[0] for a in ACTION_TYPES],
                format_func=lambda x: dict(ACTION_TYPES).get(x, x),
            )

            channel = st.selectbox(
                "Channel",
                options=["", "Google Ads", "Meta Ads", "Klaviyo", "Organic", "All"],
            )

        with col2:
            percent_change = st.number_input(
                "% Change (optional)",
                min_value=-100.0,
                max_value=1000.0,
                value=0.0,
                step=5.0,
            )

            amount = st.number_input(
                "$ Amount (optional)",
                min_value=0.0,
                value=0.0,
                step=100.0,
            )

        description = st.text_input(
            "What did you do?",
            placeholder="e.g., Increased Meta TOF budget by 15%",
        )

        campaign = st.text_input(
            "Campaign name (optional)",
            placeholder="e.g., TOF Testing CBO - Prospecting",
        )

        notes = st.text_area(
            "Notes (optional)",
            placeholder="Why did you make this change? What do you expect to happen?",
        )

        submitted = st.form_submit_button("Log Action", type="primary")

        if submitted and description:
            entry = add_entry(
                action_type=action_type,
                description=description,
                channel=channel if channel else None,
                campaign=campaign if campaign else None,
                amount=amount if amount > 0 else None,
                percent_change=percent_change if percent_change != 0 else None,
                notes=notes if notes else None,
                metrics_snapshot=current_metrics,
            )
            st.success(f"Logged: {description}")
            st.rerun()

    st.markdown("---")

    # Display recent entries
    st.subheader("Recent Activity")

    entries = get_recent_entries(days=90, limit=50)

    if not entries:
        st.info("No activity logged yet. Start by logging your first action above.")
    else:
        for entry in entries:
            timestamp = entry.get("timestamp", "")[:16].replace("T", " ")
            action_type = entry.get("action_type", "other")
            action_label = dict(ACTION_TYPES).get(action_type, action_type)
            description = entry.get("description", "")
            channel = entry.get("channel", "")
            campaign = entry.get("campaign", "")
            percent = entry.get("percent_change")
            amount = entry.get("amount")
            notes = entry.get("notes", "")
            metrics = entry.get("metrics_snapshot", {})

            # Color based on action type
            if "increase" in action_type or "launched" in action_type:
                color = "#4caf50"
            elif "decrease" in action_type or "paused" in action_type:
                color = "#f44336"
            else:
                color = "#2196f3"

            # Build details string
            details = []
            if channel:
                details.append(channel)
            if percent:
                details.append(f"{percent:+.0f}%")
            if amount:
                details.append(f"${amount:,.0f}")

            details_str = " | ".join(details) if details else ""

            with st.container():
                col1, col2 = st.columns([0.9, 0.1])

                with col1:
                    st.markdown(f"""
                    <div style="background: {color}15; border-left: 4px solid {color}; padding: 12px; border-radius: 4px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong>{description}</strong>
                            <span style="color: #888; font-size: 0.85em;">{timestamp}</span>
                        </div>
                        <div style="color: #888; font-size: 0.9em; margin-top: 4px;">
                            {action_label}{(' - ' + details_str) if details_str else ''}
                        </div>
                        {f'<div style="color: #888; font-size: 0.85em; margin-top: 4px;"><em>Campaign: {campaign}</em></div>' if campaign else ''}
                        {f'<div style="color: #aaa; font-size: 0.85em; margin-top: 4px;">{notes}</div>' if notes else ''}
                        {f'<div style="color: #666; font-size: 0.8em; margin-top: 4px;">CAM/Order: ${metrics.get("cam_per_order", 0):.2f} at time of change</div>' if metrics.get("cam_per_order") else ''}
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    if st.button("X", key=f"delete_{entry.get('id')}"):
                        delete_entry(entry.get("id"))
                        st.rerun()

    # Summary stats
    if entries:
        st.markdown("---")
        st.subheader("Summary")

        col1, col2, col3 = st.columns(3)

        spend_increases = sum(1 for e in entries if e.get("action_type") == "spend_increase")
        spend_decreases = sum(1 for e in entries if e.get("action_type") == "spend_decrease")
        total_actions = len(entries)

        with col1:
            st.metric("Total Actions Logged", total_actions)

        with col2:
            st.metric("Spend Increases", spend_increases)

        with col3:
            st.metric("Spend Decreases", spend_decreases)
