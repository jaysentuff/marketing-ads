"""
Action Board - Specific, Actionable Tasks with Auto-Logging

Shows exactly which campaigns to adjust and by how much.
Checkboxes auto-log to changelog when submitted.
"""

import streamlit as st
from datetime import datetime

from data_loader import (
    get_latest_report,
    get_decision_signals,
    get_kendall_attribution,
    format_currency,
)
from changelog import add_entry


def calculate_budget_recommendation(current_spend: float, roas: float, action_type: str) -> dict:
    """
    Calculate specific budget change recommendation.

    For scaling (high ROAS): Increase by 15-25% depending on ROAS
    For cutting (low ROAS): Decrease by 20-30% depending on severity
    """
    if action_type == "scale":
        if roas >= 4.0:
            pct = 25
        elif roas >= 3.5:
            pct = 20
        else:
            pct = 15
        change = current_spend * (pct / 100)
        return {
            "percent": pct,
            "amount": change,
            "new_budget": current_spend + change,
            "direction": "increase"
        }
    else:  # cut
        if roas < 1.0:
            pct = 30
        elif roas < 1.5:
            pct = 25
        else:
            pct = 20
        change = current_spend * (pct / 100)
        return {
            "percent": pct,
            "amount": change,
            "new_budget": current_spend - change,
            "direction": "decrease"
        }


def get_campaign_spend(channel: str, campaign_name: str) -> float:
    """Get campaign spend from attribution data."""
    attribution = get_kendall_attribution()
    if not attribution:
        return 0

    channel_data = attribution.get(channel, {})
    breakdowns = channel_data.get("breakdowns", {})
    campaign_data = breakdowns.get(campaign_name, {})

    # Estimate daily spend from revenue and ROAS
    revenue = campaign_data.get("sales", 0)
    roas = campaign_data.get("roas", 2)
    if roas > 0 and revenue > 0:
        return revenue / roas / 30  # Approximate daily spend
    return 50  # Default daily budget assumption


def render():
    st.title("⚡ Action Board")
    st.markdown("**Specific actions with budget amounts** - Check off and submit to log")

    report = get_latest_report()

    if not report:
        st.error("No data. Run: `python E:/VS Code/Marketing Ads/connectors/pull_all_data.py`")
        return

    signals = get_decision_signals()
    r = report.get("report", {})
    summary = r.get("summary", {})
    cam_per_order = summary.get("blended_cam_per_order", 0)

    # Initialize session state for tracking completed actions
    if "completed_actions" not in st.session_state:
        st.session_state.completed_actions = set()

    if "action_log_success" not in st.session_state:
        st.session_state.action_log_success = False

    # Build specific action items with budget amounts
    actions = []
    action_id = 0

    # 1. Campaigns to SCALE (high performers)
    scale_campaigns = signals.get("campaigns_to_scale", [])[:5]
    for c in scale_campaigns:
        daily_spend = get_campaign_spend(c["channel"], c["name"])
        rec = calculate_budget_recommendation(daily_spend, c["roas"], "scale")

        action_id += 1
        actions.append({
            "id": f"scale_{action_id}",
            "priority": "HIGH",
            "action_type": "spend_increase",
            "action": f"INCREASE: {c['name'][:45]}",
            "campaign": c["name"],
            "channel": c["channel"],
            "reason": f"{c['roas']:.1f}x ROAS | {c['orders']} orders | {c.get('nc_pct', 0)*100:.0f}% new customers",
            "budget_change": f"+${rec['amount']:.0f}/day (+{rec['percent']}%)",
            "budget_amount": rec['amount'],
            "budget_percent": rec['percent'],
            "new_budget": f"${rec['new_budget']:.0f}/day",
            "color": "#4caf50",
            "icon": "📈"
        })

    # 2. Campaigns to CUT (poor performers)
    watch_campaigns = signals.get("campaigns_to_watch", [])[:5]
    for c in watch_campaigns:
        daily_spend = get_campaign_spend(c["channel"], c["name"])
        rec = calculate_budget_recommendation(daily_spend, c["roas"], "cut")

        action_id += 1
        actions.append({
            "id": f"cut_{action_id}",
            "priority": "MEDIUM",
            "action_type": "spend_decrease",
            "action": f"DECREASE: {c['name'][:45]}",
            "campaign": c["name"],
            "channel": c["channel"],
            "reason": f"Only {c['roas']:.1f}x ROAS | {c['orders']} orders | {c.get('note', 'Underperforming')}",
            "budget_change": f"-${rec['amount']:.0f}/day (-{rec['percent']}%)",
            "budget_amount": -rec['amount'],
            "budget_percent": -rec['percent'],
            "new_budget": f"${rec['new_budget']:.0f}/day",
            "color": "#f44336",
            "icon": "📉"
        })

    # 3. Channel budget shift if recommended
    shift = signals.get("channel_shift")
    if shift:
        action_id += 1
        # Calculate shift amount (10% of lower-performing channel)
        shift_amount = summary.get("total_ad_spend", 10000) * 0.10 / 30  # 10% of monthly spend, daily
        actions.append({
            "id": f"shift_{action_id}",
            "priority": "MEDIUM",
            "action_type": "budget_shift",
            "action": f"SHIFT BUDGET: {shift['from']} → {shift['to']}",
            "campaign": f"{shift['from']} to {shift['to']}",
            "channel": "Cross-Channel",
            "reason": shift['reason'],
            "budget_change": f"Move ${shift_amount:.0f}/day",
            "budget_amount": shift_amount,
            "budget_percent": 10,
            "new_budget": "",
            "color": "#2196f3",
            "icon": "🔄"
        })

    # 4. TOF-specific actions
    tof = signals.get("tof_assessment")
    if tof:
        verdict = tof.get("verdict", "")
        if verdict == "needs_review":
            action_id += 1
            actions.append({
                "id": f"tof_{action_id}",
                "priority": "LOW",
                "action_type": "other",
                "action": "REVIEW TOF Campaigns (Don't cut yet!)",
                "campaign": "TOF Prospecting",
                "channel": "Meta Ads",
                "reason": f"NCAC ${tof.get('ncac_7d_avg', 0):.0f} | Branded search {tof.get('branded_search_pct', 0):.0f}% - check correlation",
                "budget_change": "No change yet",
                "budget_amount": 0,
                "budget_percent": 0,
                "new_budget": "Pending review",
                "color": "#ff9800",
                "icon": "🔍"
            })
        elif verdict == "healthy":
            action_id += 1
            # TOF healthy - consider small increase
            tof_increase = 20  # $20/day
            actions.append({
                "id": f"tof_{action_id}",
                "priority": "LOW",
                "action_type": "spend_increase",
                "action": "MAINTAIN/TEST TOF (It's working!)",
                "campaign": "TOF Prospecting",
                "channel": "Meta Ads",
                "reason": f"NCAC ${tof.get('ncac_7d_avg', 0):.0f} (under $50 target) | Test small increase",
                "budget_change": f"+${tof_increase}/day (test)",
                "budget_amount": tof_increase,
                "budget_percent": 10,
                "new_budget": "",
                "color": "#4caf50",
                "icon": "✅"
            })

    # Display actions with checkboxes
    if not actions:
        st.success("**All clear!** No urgent actions today. CAM is stable at " + format_currency(cam_per_order))
    else:
        # Show success message if just logged
        if st.session_state.action_log_success:
            st.success("✅ Actions logged to changelog successfully!")
            st.session_state.action_log_success = False

        # Group by priority
        high = [a for a in actions if a["priority"] == "HIGH"]
        medium = [a for a in actions if a["priority"] == "MEDIUM"]
        low = [a for a in actions if a["priority"] == "LOW"]

        # Track which checkboxes are checked
        checked_actions = []

        if high:
            st.markdown("### 🔴 DO NOW (High-Performing Campaigns)")
            for a in high:
                checked = render_action_card(a)
                if checked:
                    checked_actions.append(a)

        if medium:
            st.markdown("### 🟡 DO TODAY (Needs Attention)")
            for a in medium:
                checked = render_action_card(a)
                if checked:
                    checked_actions.append(a)

        if low:
            st.markdown("### 🟢 OPTIONAL (Monitor)")
            for a in low:
                checked = render_action_card(a)
                if checked:
                    checked_actions.append(a)

        # Submit button
        st.markdown("---")

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            if checked_actions:
                st.info(f"**{len(checked_actions)} action(s) selected** - Click submit to log to changelog")
            else:
                st.caption("Check off completed actions, then click Submit")

        with col2:
            if st.button("📝 Submit Completed", type="primary", use_container_width=True, disabled=len(checked_actions) == 0):
                log_actions_to_changelog(checked_actions, summary)
                st.session_state.action_log_success = True
                st.rerun()

        with col3:
            if st.button("🔄 Reset Checkboxes", use_container_width=True):
                # Clear all checkbox states
                for key in list(st.session_state.keys()):
                    if key.startswith("action_"):
                        del st.session_state[key]
                st.rerun()

    # Quick stats at bottom
    st.markdown("---")
    st.markdown("### Quick Stats")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        target = 20
        delta = cam_per_order - target
        st.metric(
            "CAM/Order",
            format_currency(cam_per_order),
            delta=f"{delta:+.2f} vs target",
            delta_color="normal" if delta >= 0 else "inverse"
        )

    with col2:
        total_orders = summary.get("total_orders", 0)
        st.metric("Orders (30d)", f"{total_orders:,}")

    with col3:
        ad_spend = summary.get("total_ad_spend", 0)
        st.metric("Ad Spend (30d)", format_currency(ad_spend))

    with col4:
        spend_decision = signals.get("spend_decision", "hold")
        decision_emoji = {"increase": "📈", "decrease": "📉", "hold": "⏸️"}
        st.metric("Overall Signal", f"{decision_emoji.get(spend_decision, '')} {spend_decision.upper()}")

    # Report time
    generated_at = report.get("generated_at", "Unknown")
    st.caption(f"Data from: {generated_at}")


def render_action_card(action: dict) -> bool:
    """Render a single action card with checkbox. Returns True if checked."""
    key = f"action_{action['id']}"

    col1, col2 = st.columns([0.06, 0.94])

    with col1:
        checked = st.checkbox("", key=key, label_visibility="collapsed")

    with col2:
        # Strikethrough if checked
        text_style = "text-decoration: line-through; opacity: 0.6;" if checked else ""

        st.markdown(f"""
        <div style="background: {action['color']}15; border-left: 4px solid {action['color']};
                    padding: 12px 16px; border-radius: 4px; margin-bottom: 8px; {text_style}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <strong style="font-size: 1.1em;">{action['icon']} {action['action']}</strong>
                    <span style="background: {action['color']}30; padding: 2px 8px; border-radius: 4px; margin-left: 8px; font-size: 0.85em;">
                        {action['channel']}
                    </span>
                </div>
                <div style="text-align: right;">
                    <span style="background: {action['color']}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;">
                        {action['budget_change']}
                    </span>
                </div>
            </div>
            <div style="color: #666; margin-top: 6px; font-size: 0.9em;">
                {action['reason']}
            </div>
            {f'<div style="color: #888; margin-top: 4px; font-size: 0.85em;">New daily budget: {action["new_budget"]}</div>' if action['new_budget'] else ''}
        </div>
        """, unsafe_allow_html=True)

    return checked


def log_actions_to_changelog(actions: list, summary: dict):
    """Log all completed actions to the changelog."""

    metrics_snapshot = {
        "cam_per_order": summary.get("blended_cam_per_order", 0),
        "total_orders": summary.get("total_orders", 0),
        "total_ad_spend": summary.get("total_ad_spend", 0),
        "total_cam": summary.get("blended_cam", 0),
    }

    for action in actions:
        # Build description
        if action['budget_amount'] != 0:
            if action['budget_amount'] > 0:
                desc = f"Increased budget +${abs(action['budget_amount']):.0f}/day (+{abs(action['budget_percent'])}%)"
            else:
                desc = f"Decreased budget -${abs(action['budget_amount']):.0f}/day (-{abs(action['budget_percent'])}%)"
        else:
            desc = action['action']

        add_entry(
            action_type=action['action_type'],
            description=desc,
            channel=action['channel'],
            campaign=action['campaign'],
            amount=abs(action['budget_amount']) if action['budget_amount'] != 0 else None,
            percent_change=action['budget_percent'] if action['budget_percent'] != 0 else None,
            notes=f"ROAS-based recommendation from Action Board. Reason: {action['reason'][:100]}",
            metrics_snapshot=metrics_snapshot,
        )
