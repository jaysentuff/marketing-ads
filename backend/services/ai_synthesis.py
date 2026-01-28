"""
AI Synthesis Service.

This is the brain of the autonomous marketing optimization system.
It reasons over multiple signals to generate nuanced recommendations,
and learns from past decisions through the feedback loop.

Key principles:
1. No single metric tells the truth - triangulate signals
2. Past recommendations and outcomes inform future decisions
3. TOF campaigns are measured differently than direct response
4. Provide reasoning, not just recommendations
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / "connectors" / ".env")

from services.data_loader import (
    get_latest_report,
    get_decision_signals,
    get_blended_metrics,
    get_spend_outcome_correlation,
    get_channel_correlation,
)
from services.multi_signal import (
    get_multi_signal_campaign_view,
    get_cross_channel_correlation,
    get_campaign_for_llm_context,
)
from services.recommendations import (
    get_recommendation_summary_for_llm,
    add_recommendation,
    get_pending_recommendations,
)
from services.changelog import get_entries_summary

EST = ZoneInfo("America/New_York")

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


SYNTHESIS_SYSTEM_PROMPT = """You are the AI Chief Marketing Officer (ACMO) for TuffWraps, an e-commerce fitness accessories brand.

Your job is to analyze marketing performance data from multiple sources and provide actionable recommendations with clear reasoning.

## CRITICAL PRINCIPLES

1. **NO SINGLE METRIC TELLS THE TRUTH**
   - Platform-reported ROAS is inflated (platforms over-claim credit)
   - Kendall last-click misses awareness/assist value
   - Kendall first-click misses conversion optimization value
   - You must triangulate all signals to form a judgment

2. **TOF CAMPAIGNS ARE DIFFERENT**
   - Top-of-funnel ads drive awareness, not immediate conversions
   - A customer sees a TOF ad, then Googles the brand later
   - Meta TOF spend correlates with Google branded search (with lag)
   - Measure TOF by: NCAC, first-click ROAS, branded search correlation, session quality
   - DO NOT recommend cutting TOF based on low direct ROAS alone

3. **LEARN FROM PAST DECISIONS**
   - You will see summaries of past recommendations and their outcomes
   - If scaling a campaign type consistently led to negative outcomes, be cautious
   - If cutting TOF hurt branded search before, don't repeat that mistake
   - When recommendations were ignored, understand why before repeating them

4. **WEIGHTED SIGNAL APPROACH**
   Use these weights when evaluating campaigns:
   - Kendall Last-Click ROAS: 30% (most de-duplicated)
   - Kendall First-Click ROAS: 20% (awareness credit)
   - Platform ROAS: 15% (has view-through, but self-interested)
   - Session Quality: 25% (bounce rate, ATC rate, order rate)
   - Trend: 10% (is it improving or declining?)

5. **DECISION THRESHOLDS**
   - CAM per order > $24: Consider scaling
   - CAM per order < $16: Consider cutting
   - NCAC > $50: Acquisition too expensive
   - MER < 3.0: Overall efficiency too low
   - Weighted score > 0.6: Strong performer
   - Weighted score < 0.3 with $100+ spend: Underperformer

## OUTPUT FORMAT

Provide your analysis in this structure:

### Executive Summary
[2-3 sentences on overall marketing health and key insight]

### Key Findings
[3-5 bullet points of important observations]

### Recommendations

For each recommendation, provide:

**[ACTION]: [Campaign/Channel Name]**
- What: [Specific action with dollar amounts or percentages]
- Why: [Multi-signal reasoning - cite specific metrics]
- Confidence: [High/Medium/Low]
- Signals considered: [List which signals informed this]
- Risk: [What could go wrong]
- Monitor: [What to watch after implementing]

### Learning from Past Decisions
[If past recommendation data is provided, note any patterns or lessons]

### Questions/Uncertainties
[Any areas where you need more data or where the signals conflict]

## IMPORTANT CONSTRAINTS

- Be specific: "$150/day increase" not "increase budget"
- Be honest about uncertainty - it's okay to say "need more data"
- Don't recommend the same action that failed before without new evidence
- If signals strongly conflict, recommend a test rather than a big commitment
- Always consider the cross-channel effect before cutting TOF"""


def build_synthesis_context(days: int = 30) -> str:
    """
    Build comprehensive context for LLM synthesis.

    This gathers all available signals and formats them for the LLM.
    """
    lines = [
        "=" * 60,
        "MARKETING PERFORMANCE DATA FOR ANALYSIS",
        f"Generated: {datetime.now(EST).strftime('%Y-%m-%d %H:%M:%S')} EST",
        "=" * 60,
        "",
    ]

    # 1. Overall Performance Summary
    report = get_latest_report()
    if report:
        r = report.get("report", {})
        summary = r.get("summary", {})

        lines.extend([
            "## OVERALL PERFORMANCE (Last 30 Days)",
            "",
            f"- Total Revenue: ${summary.get('total_revenue', 0):,.2f}",
            f"- Total Orders: {summary.get('total_orders', 0):,}",
            f"- Total Ad Spend: ${summary.get('total_ad_spend', 0):,.2f}",
            f"- Blended CAM: ${summary.get('blended_cam', 0):,.2f}",
            f"- CAM per Order: ${summary.get('blended_cam_per_order', 0):.2f} (Target: $20)",
            "",
        ])

    # 2. Signal Triangulation (Spend-to-Outcome)
    try:
        correlation = get_spend_outcome_correlation(days=14)
        if "error" not in correlation:
            lines.extend([
                "## SIGNAL TRIANGULATION (Last 14 days vs. prior 14 days)",
                "",
                f"Spend direction: {correlation['spend_direction'].upper()}",
                f"Spend change: {correlation['changes']['ad_spend_pct']:+.1f}%",
                "",
                "Signal Agreement:",
            ])

            for signal in correlation.get("signals", []):
                emoji = "+" if signal["agreement"] == "agree" else "-" if signal["agreement"] == "disagree" else "~"
                lines.append(f"  {emoji} {signal['label']}: {signal['change_pct']:+.1f}% ({signal['agreement']})")

            lines.extend([
                "",
                f"Verdict: {correlation['verdict']['status'].upper()}",
                f"Message: {correlation['verdict']['message']}",
                "",
                "Efficiency Metrics:",
                f"  - Current MER: {correlation['efficiency']['current_mer']:.2f}x (floor: 3.0x)",
                f"  - Current NCAC: ${correlation['efficiency']['current_ncac']:.2f} (ceiling: $50)",
                f"  - MER change: {correlation['efficiency']['mer_change_pct']:+.1f}%",
                f"  - NCAC change: {correlation['efficiency']['ncac_change_pct']:+.1f}%",
                "",
            ])
    except Exception as e:
        lines.append(f"(Signal triangulation unavailable: {e})")
        lines.append("")

    # 3. Cross-Channel Correlation
    try:
        cross_channel = get_cross_channel_correlation(days=30)
        if "error" not in cross_channel:
            lines.extend([
                "## CROSS-CHANNEL CORRELATION",
                "",
                f"Meta Spend to Branded Search Correlation: {cross_channel['best_meta_to_branded']['correlation']:.2f}",
                f"  - Strength: {cross_channel['best_meta_to_branded']['strength']}",
                f"  - Optimal lag: {cross_channel['best_meta_to_branded']['optimal_lag_days']} days",
                "",
                f"Meta Spend to Google First-Click Correlation: {cross_channel['best_meta_to_google_fc']['correlation']:.2f}",
                f"  - Strength: {cross_channel['best_meta_to_google_fc']['strength']}",
                f"  - Optimal lag: {cross_channel['best_meta_to_google_fc']['optimal_lag_days']} days",
                "",
            ])

            for interp in cross_channel.get("interpretation", []):
                lines.append(f"  * {interp}")

            lines.append(f"\nImplication: {cross_channel.get('implication', '')}")
            lines.append("")
    except Exception as e:
        lines.append(f"(Cross-channel correlation unavailable: {e})")
        lines.append("")

    # 4. Multi-Signal Campaign Analysis
    try:
        lines.append("## META ADS MULTI-SIGNAL ANALYSIS")
        lines.append("")
        meta_analysis = get_campaign_for_llm_context("facebook", days)
        lines.append(meta_analysis)
        lines.append("")
    except Exception as e:
        lines.append(f"(Meta analysis unavailable: {e})")
        lines.append("")

    try:
        lines.append("## GOOGLE ADS MULTI-SIGNAL ANALYSIS")
        lines.append("")
        google_analysis = get_campaign_for_llm_context("google", days)
        lines.append(google_analysis)
        lines.append("")
    except Exception as e:
        lines.append(f"(Google analysis unavailable: {e})")
        lines.append("")

    # 5. TOF Assessment
    signals = get_decision_signals()
    tof = signals.get("tof_assessment")
    if tof:
        lines.extend([
            "## TOF (TOP-OF-FUNNEL) ASSESSMENT",
            "",
            "IMPORTANT: TOF campaigns should NOT be judged by direct ROAS alone.",
            "",
            f"- Meta First-Click Revenue (7d): ${tof.get('meta_first_click_7d', 0):,.2f}",
            f"- Blended NCAC: ${tof.get('ncac_7d_avg', 0):.2f} (Target: <$50)",
            f"- Branded Search %: {tof.get('branded_search_pct', 0):.1f}%",
            f"- Amazon Halo Sales (7d): ${tof.get('amazon_sales_7d', 0):,.2f}",
            f"- Amazon Trend: {tof.get('amazon_trend', 0):+.1f}%",
            "",
            f"TOF Verdict: {tof.get('verdict', 'unknown').upper()}",
            f"Assessment: {tof.get('message', '')}",
            "",
        ])

    # 6. Recent Activity
    lines.extend([
        "## RECENT ACTIONS TAKEN",
        "",
        get_entries_summary(),
        "",
    ])

    # 7. Past Recommendations and Outcomes (THE FEEDBACK LOOP)
    try:
        rec_summary = get_recommendation_summary_for_llm(days=30)
        lines.extend([
            "## PAST AI RECOMMENDATIONS & OUTCOMES",
            "",
            rec_summary.get("summary", "No past recommendations recorded."),
            "",
        ])

        # Show examples if available
        examples = rec_summary.get("examples", [])
        if examples:
            lines.append("Examples:")
            for ex in examples:
                if ex["type"] == "success":
                    lines.append(f"  SUCCESS: {ex['recommendation']} -> {ex.get('metrics_change', 'N/A')}")
                elif ex["type"] == "failure":
                    lines.append(f"  FAILURE: {ex['recommendation']} -> {ex.get('metrics_change', 'N/A')}")
                elif ex["type"] == "ignored":
                    lines.append(f"  IGNORED: {ex['recommendation']} (Reason: {ex.get('reason_ignored', 'None given')})")
            lines.append("")

        # Show patterns
        patterns = rec_summary.get("patterns", [])
        if patterns:
            lines.append("Patterns observed:")
            for p in patterns:
                lines.append(f"  - {p}")
            lines.append("")
    except Exception as e:
        lines.append(f"(Past recommendations unavailable: {e})")
        lines.append("")

    # 8. Pending Recommendations
    try:
        pending = get_pending_recommendations(days=7)
        if pending:
            lines.extend([
                "## PENDING RECOMMENDATIONS (Not yet acted upon)",
                "",
            ])
            for rec in pending[:5]:
                lines.append(f"- {rec.get('action', 'Unknown')} ({rec.get('channel', '')})")
                lines.append(f"  Reason: {rec.get('reason', '')}")
                lines.append(f"  Created: {rec.get('created_at', '')[:10]}")
            lines.append("")
    except Exception:
        pass

    return "\n".join(lines)


async def generate_synthesis(
    user_question: Optional[str] = None,
    days: int = 30,
    save_recommendations: bool = True,
) -> dict:
    """
    Generate AI synthesis of marketing performance with recommendations.

    Args:
        user_question: Optional specific question to answer
        days: Number of days to analyze
        save_recommendations: Whether to save generated recommendations for tracking

    Returns:
        Dictionary with synthesis results
    """
    if not ANTHROPIC_AVAILABLE:
        return {"error": "Anthropic library not installed"}

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    # Build context
    context = build_synthesis_context(days)

    # Build the user message
    if user_question:
        user_message = f"""Here is the current marketing data and performance metrics:

{context}

---

Based on this data, please answer my question:

{user_question}

Provide your analysis following the output format in your instructions."""
    else:
        user_message = f"""Here is the current marketing data and performance metrics:

{context}

---

Please provide a comprehensive analysis and actionable recommendations.
Follow the output format in your instructions.

Focus on:
1. What are the top 3-5 actions to take right now?
2. What campaigns should be scaled, maintained, or cut?
3. How is TOF performing and should we adjust it?
4. Are there any concerning trends we need to address?
5. What learnings from past recommendations should inform our decisions?"""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYNTHESIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        synthesis_text = response.content[0].text

        # Parse recommendations from the response (simplified extraction)
        recommendations_extracted = _extract_recommendations(synthesis_text)

        # Save recommendations if requested
        saved_recommendations = []
        if save_recommendations and recommendations_extracted:
            # Get current metrics for the snapshot
            report = get_latest_report()
            summary = report.get("report", {}).get("summary", {}) if report else {}
            correlation = get_spend_outcome_correlation(days=14)
            efficiency = correlation.get("efficiency", {}) if "error" not in correlation else {}

            metrics_snapshot = {
                "cam_per_order": summary.get("blended_cam_per_order", 0),
                "mer": efficiency.get("current_mer", 0),
                "ncac": efficiency.get("current_ncac", 0),
                "total_spend": summary.get("total_ad_spend", 0),
                "total_revenue": summary.get("total_revenue", 0),
            }

            for rec in recommendations_extracted:
                saved = add_recommendation(
                    recommendation_type=rec.get("type", "other"),
                    action=rec.get("action", ""),
                    channel=rec.get("channel"),
                    campaign=rec.get("campaign"),
                    budget_change_amount=rec.get("budget_amount"),
                    budget_change_percent=rec.get("budget_percent"),
                    reason=rec.get("reason", ""),
                    confidence=rec.get("confidence", "medium"),
                    signals_used=rec.get("signals", []),
                    metrics_at_recommendation=metrics_snapshot,
                    llm_reasoning=rec.get("full_reasoning", ""),
                )
                saved_recommendations.append(saved)

        return {
            "success": True,
            "synthesis": synthesis_text,
            "recommendations_extracted": recommendations_extracted,
            "recommendations_saved": len(saved_recommendations),
            "context_summary": {
                "days_analyzed": days,
                "context_length": len(context),
            },
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "generated_at": datetime.now(EST).isoformat(),
        }

    except Exception as e:
        return {"error": str(e)}


def _extract_recommendations(synthesis_text: str) -> list[dict]:
    """
    Extract structured recommendations from the synthesis text.

    This is a simplified extraction - in production you might use
    structured output or more sophisticated parsing.
    """
    recommendations = []

    # Look for recommendation patterns
    lines = synthesis_text.split("\n")
    current_rec = None

    for line in lines:
        line = line.strip()

        # Look for recommendation headers
        if line.startswith("**") and ":" in line:
            if any(action in line.upper() for action in ["SCALE", "CUT", "MAINTAIN", "HOLD", "INCREASE", "DECREASE", "REDUCE", "REVIEW", "TEST"]):
                # Save previous recommendation
                if current_rec:
                    recommendations.append(current_rec)

                # Start new recommendation
                action_type = "other"
                if "SCALE" in line.upper() or "INCREASE" in line.upper():
                    action_type = "scale"
                elif "CUT" in line.upper() or "DECREASE" in line.upper() or "REDUCE" in line.upper():
                    action_type = "cut"
                elif "HOLD" in line.upper() or "MAINTAIN" in line.upper():
                    action_type = "hold"
                elif "TEST" in line.upper():
                    action_type = "test"

                current_rec = {
                    "type": action_type,
                    "action": line.replace("**", "").strip(),
                    "channel": None,
                    "campaign": None,
                    "reason": "",
                    "confidence": "medium",
                    "signals": [],
                    "budget_amount": None,
                    "budget_percent": None,
                    "full_reasoning": "",
                }

                # Try to extract channel
                if "Meta" in line or "Facebook" in line:
                    current_rec["channel"] = "Meta Ads"
                elif "Google" in line:
                    current_rec["channel"] = "Google Ads"

        # Extract details from current recommendation
        if current_rec:
            current_rec["full_reasoning"] += line + "\n"

            if line.lower().startswith("- what:"):
                current_rec["action"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("- why:"):
                current_rec["reason"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("- confidence:"):
                conf = line.split(":", 1)[1].strip().lower()
                if "high" in conf:
                    current_rec["confidence"] = "high"
                elif "low" in conf:
                    current_rec["confidence"] = "low"
            elif line.lower().startswith("- signals"):
                current_rec["signals"].append(line.split(":", 1)[1].strip())

            # Try to extract budget amounts
            if "$" in line and "/day" in line.lower():
                import re
                amount_match = re.search(r'\$(\d+(?:,\d+)?(?:\.\d+)?)', line)
                if amount_match:
                    try:
                        current_rec["budget_amount"] = float(amount_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

            if "%" in line and current_rec["budget_percent"] is None:
                import re
                pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
                if pct_match:
                    try:
                        current_rec["budget_percent"] = float(pct_match.group(1))
                    except ValueError:
                        pass

    # Don't forget the last recommendation
    if current_rec:
        recommendations.append(current_rec)

    return recommendations


def get_synthesis_status() -> dict:
    """Check if AI synthesis is available and configured."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "available": ANTHROPIC_AVAILABLE and bool(api_key),
        "anthropic_installed": ANTHROPIC_AVAILABLE,
        "api_key_configured": bool(api_key),
    }
