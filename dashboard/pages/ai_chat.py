"""
AI Marketing Assistant - Chat with Claude about your marketing data.

Uses Anthropic's Claude API to analyze your marketing metrics,
suggest optimizations, and reference your activity history.
"""

import streamlit as st
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from connectors/.env
load_dotenv(Path(__file__).parent.parent.parent / "connectors" / ".env")

from data_loader import (
    get_latest_report,
    get_decision_signals,
    get_blended_metrics,
    format_currency,
)
from changelog import get_entries_summary

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def get_marketing_context() -> str:
    """Build context string from current marketing data."""
    report = get_latest_report()
    if not report:
        return "No marketing data available yet."

    r = report.get("report", {})
    summary = r.get("summary", {})
    channels = r.get("channels", {})
    signals = get_decision_signals()
    blended = get_blended_metrics()

    # Build context
    lines = [
        "=== CURRENT MARKETING DATA ===",
        f"Report Date: {report.get('generated_at', 'Unknown')}",
        "",
        "--- Overall Performance (Last 30 Days) ---",
        f"Total Orders: {summary.get('total_orders', 0):,}",
        f"Total Revenue: ${summary.get('total_revenue', 0):,.2f}",
        f"Total Ad Spend: ${summary.get('total_ad_spend', 0):,.2f}",
        f"Blended CAM: ${summary.get('blended_cam', 0):,.2f}",
        f"CAM per Order: ${summary.get('blended_cam_per_order', 0):.2f} (Target: $20)",
        "",
        "--- Channel Performance ---",
    ]

    for channel_name, data in channels.items():
        lines.append(f"{channel_name}:")
        lines.append(f"  - Orders: {data.get('orders', 0):,}")
        lines.append(f"  - Revenue: ${data.get('revenue', 0):,.2f}")
        lines.append(f"  - Spend: ${data.get('spend', 0):,.2f}")
        lines.append(f"  - CAM: ${data.get('cam', 0):,.2f}")
        lines.append(f"  - ROAS: {data.get('roas', 0):.2f}x")

    # Add TOF assessment
    tof = signals.get("tof_assessment")
    if tof:
        lines.extend([
            "",
            "--- TOF (Top-of-Funnel) Assessment ---",
            "NOTE: TOF campaigns should NOT be judged by direct ROAS.",
            "Instead, look at first-click attribution, branded search, and NCAC.",
            f"Meta First-Click (7d): ${tof.get('meta_first_click_7d', 0):,.2f}",
            f"Blended NCAC: ${tof.get('ncac_7d_avg', 0):.2f} (Target: <$50)",
            f"Branded Search %: {tof.get('branded_search_pct', 0):.1f}%",
            f"Amazon Sales (7d): ${tof.get('amazon_sales_7d', 0):,.2f}",
            f"TOF Verdict: {tof.get('verdict', 'unknown')} - {tof.get('message', '')}",
        ])

    # Add current decision signals
    lines.extend([
        "",
        "--- Current AI Signals ---",
        f"Spend Decision: {signals.get('spend_decision', 'hold').upper()}",
    ])

    if signals.get("campaigns_to_scale"):
        lines.append("Campaigns to Scale:")
        for c in signals["campaigns_to_scale"][:5]:
            lines.append(f"  - {c['name'][:50]} ({c['channel']}) - {c['roas']:.2f}x ROAS")

    if signals.get("campaigns_to_watch"):
        lines.append("Campaigns to Watch:")
        for c in signals["campaigns_to_watch"][:5]:
            lines.append(f"  - {c['name'][:50]} ({c['channel']}) - {c['roas']:.2f}x ROAS")

    if signals.get("alerts"):
        lines.append("Alerts:")
        for alert in signals["alerts"]:
            lines.append(f"  - {alert}")

    # Add recent activity
    activity = get_entries_summary()
    lines.extend([
        "",
        "=== RECENT ACTIVITY LOG ===",
        activity,
    ])

    return "\n".join(lines)


SYSTEM_PROMPT = """You are a marketing analyst assistant for TuffWraps, an e-commerce brand selling fitness accessories.

Your role is to help analyze marketing performance and make optimization recommendations based on the data provided.

KEY CONCEPTS:
1. CAM (Contribution After Marketing) = Revenue - COGS - Shipping - Ad Spend
   - Target: $20 CAM per order
   - This is the PRIMARY metric for overall health

2. TOF (Top-of-Funnel) campaigns should NOT be evaluated by direct ROAS:
   - TOF ads create awareness - customers often don't buy immediately
   - They see the ad, then Google the brand later
   - Measure TOF by: First-click attribution, branded search trend, blended NCAC
   - Target NCAC (New Customer Acquisition Cost): <$50

3. Attribution:
   - Platform-reported ROAS is inflated (both platforms claim same conversion)
   - Use Kendall attribution for true multi-touch attribution
   - First-click shows which channel introduced the customer

4. Decision Framework:
   - CAM per order > $24 (20% above target): Consider scaling spend
   - CAM per order < $16 (20% below target): Consider cutting spend
   - In between: Hold and optimize

WHEN GIVING ADVICE:
- Be specific and actionable
- Reference the actual numbers from the data
- Consider the user's recent activity log when relevant
- Always consider TOF separately from direct response campaigns
- Don't recommend cutting TOF just because direct ROAS looks bad

Keep responses concise and focused on what action to take."""


def render():
    st.title("AI Marketing Assistant")
    st.markdown("Ask questions about your marketing performance and get AI-powered insights.")

    # Check for API key - first from env, then from session state
    env_key = os.getenv("ANTHROPIC_API_KEY", "")
    api_key = st.session_state.get("anthropic_api_key", env_key)

    # API key input in sidebar (only show if not set in env)
    with st.sidebar:
        st.markdown("---")
        st.markdown("**AI Settings**")
        if env_key:
            st.success("API key loaded from .env")
        else:
            new_key = st.text_input(
                "Anthropic API Key",
                value=api_key,
                type="password",
                help="Enter your Anthropic API key or set ANTHROPIC_API_KEY in .env"
            )
            if new_key != api_key:
                st.session_state.anthropic_api_key = new_key
                api_key = new_key

    if not ANTHROPIC_AVAILABLE:
        st.error("Anthropic library not installed. Run: `pip install anthropic`")
        return

    if not api_key:
        st.warning("Enter your Anthropic API key in the sidebar to start chatting.")
        st.info("Get an API key at: https://console.anthropic.com/")
        return

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about your marketing performance..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get marketing context
        context = get_marketing_context()

        # Build messages for API
        messages = []

        # Add context as first user message if this is the start
        if len(st.session_state.messages) == 1:
            messages.append({
                "role": "user",
                "content": f"Here is my current marketing data:\n\n{context}\n\n---\n\nMy question: {prompt}"
            })
        else:
            # Include previous conversation
            for msg in st.session_state.messages[:-1]:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current question with fresh context
            messages.append({
                "role": "user",
                "content": f"[Updated data context]\n{context}\n\n---\n\n{prompt}"
            })

        # Call Claude API
        with st.chat_message("assistant"):
            try:
                client = anthropic.Anthropic(api_key=api_key)

                with st.spinner("Thinking..."):
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1024,
                        system=SYSTEM_PROMPT,
                        messages=messages
                    )

                assistant_message = response.content[0].text
                st.markdown(assistant_message)

                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_message
                })

            except anthropic.AuthenticationError:
                st.error("Invalid API key. Please check your Anthropic API key.")
            except anthropic.RateLimitError:
                st.error("Rate limit exceeded. Please wait a moment and try again.")
            except Exception as e:
                st.error(f"Error: {str(e)}")

    # Quick action buttons
    st.markdown("---")
    st.markdown("**Quick Questions:**")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("What should I do today?", use_container_width=True):
            st.session_state.quick_question = "Based on the current data, what are the top 3 actions I should take today to improve marketing performance?"
            st.rerun()

    with col2:
        if st.button("How is TOF performing?", use_container_width=True):
            st.session_state.quick_question = "How are my TOF (top-of-funnel) campaigns performing? Should I adjust the budget?"
            st.rerun()

    with col3:
        if st.button("Explain my CAM", use_container_width=True):
            st.session_state.quick_question = "Explain my current CAM (Contribution After Marketing) and what's driving it up or down."
            st.rerun()

    # Handle quick questions
    if "quick_question" in st.session_state:
        prompt = st.session_state.quick_question
        del st.session_state.quick_question

        # Trigger the question
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Clear chat button
    if st.session_state.messages:
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
