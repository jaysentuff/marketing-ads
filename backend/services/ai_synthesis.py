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
from services.analysis_history import save_analysis as save_to_history
from services.funnel_impact import (
    build_followup_summary_for_llm,
    get_items_in_cooling_off,
    get_funnel_health_snapshot,
    get_changes_needing_followup,
    get_correlation_insights_for_llm,
    COOLING_OFF_DAYS,
)

EST = ZoneInfo("America/New_York")

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


SYNTHESIS_SYSTEM_PROMPT = """You are the AI Chief Marketing Officer (ACMO) for TuffWraps, an e-commerce fitness accessories brand.

Your job is to analyze marketing performance data from multiple sources and provide actionable recommendations with clear reasoning.

## ANALYSIS TYPE: {{ANALYSIS_TYPE}}

You are running a {{ANALYSIS_TYPE_DESCRIPTION}}.

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

3. **TIKTOK HALO EFFECT**
   - TikTok is a discovery platform with strong HALO EFFECTS
   - People see TikTok ads → search on Google → buy on website/Amazon
   - Direct ROAS on TikTok will often look low, but total impact is higher
   - Correlate TikTok spend with: branded search volume, Amazon sales, direct traffic
   - If branded search and Amazon sales rise when TikTok spend increases, the halo is working
   - TikTok Shop orders also come through Shopify (source_name: "tiktok")

4. **LEARN FROM PAST DECISIONS**
   - You will see summaries of past recommendations and their outcomes
   - If scaling a campaign type consistently led to negative outcomes, be cautious
   - If cutting TOF hurt branded search before, don't repeat that mistake
   - When recommendations were ignored, understand why before repeating them

5. **WEIGHTED SIGNAL APPROACH**
   Use these weights when evaluating campaigns:
   - Kendall Last-Click ROAS: 30% (most de-duplicated)
   - Kendall First-Click ROAS: 20% (awareness credit)
   - Platform ROAS: 15% (has view-through, but self-interested)
   - Session Quality: 25% (bounce rate, ATC rate, order rate)
   - Trend: 10% (is it improving or declining?)

6. **MULTI-TIMEFRAME ANALYSIS**
   - 3d & 7d = ACTION windows (make scaling decisions based on these)
   - 14d & 30d = VALIDATION windows (confirm overall strategy is working)
   - When 7d ROAS >> 30d ROAS: Campaign is improving, consider scaling
   - When 7d ROAS << 30d ROAS: Campaign is declining, investigate before cutting

7. **CONFIDENCE LEVELS**
   Based on SPEND (not order count - ROAS normalizes by spend):
   - High ($500+ spend): Confident in ROAS metrics
   - Medium ($200-500 spend): Metrics are directionally correct
   - Low ($50-200 spend): Metrics are noisy, need more data
   - Very Low (<$50 spend): Cannot make reliable decisions, gather data

8. **BUDGET CONCENTRATION (CBO Campaigns)**
   - If one adset has >60% of campaign spend, Meta is over-concentrating
   - Check if the concentrated adset is the best performer
   - If NOT the best performer, recommend switching to ABO for testing
   - If IS the best performer, the CBO is working correctly

9. **DECISION THRESHOLDS**
   - CAM per order > $24: Consider scaling
   - CAM per order < $16: Consider cutting
   - NCAC > $50: Acquisition too expensive
   - MER < 3.0: Overall efficiency too low
   - Weighted score > 0.6: Strong performer
   - Weighted score < 0.3 with $100+ spend: Underperformer

10. **COOLING OFF PERIOD**
    - Items changed in the last 3 days are in "cooling off" - don't recommend changes to them
    - Give changes time to show impact before adjusting again
    - This prevents over-optimization and whipsawing

11. **FUNNEL IMPACT > SINGLE PLATFORM ROAS**
    - A spend change that hurts platform ROAS but increases branded search + total revenue = GOOD
    - A spend cut that improves platform ROAS but tanks branded search + new customers = BAD
    - Always look at the FULL FUNNEL: branded search, email signups, retargeting, total revenue

12. **SIGNAL PREDICTIVENESS (Data-Driven Weights)**
    - You will see correlation analysis showing which signals actually predict revenue
    - If branded search has WEAK correlation with revenue, don't weight it heavily
    - If Amazon has STRONG correlation with Shopify revenue, consider it a true indicator
    - Use the suggested weight adjustments to calibrate your recommendations
    - When in doubt, trust the signals that have proven predictive over multiple weeks

## OUTPUT FORMAT

{{OUTPUT_FORMAT}}

## IMPORTANT CONSTRAINTS

- Be specific: "$150/day increase" not "increase budget"
- Be honest about uncertainty - it's okay to say "need more data"
- Don't recommend the same action that failed before without new evidence
- If signals strongly conflict, recommend a test rather than a big commitment
- Always consider the cross-channel effect before cutting TOF
- NEVER recommend changes to items in cooling off period (changed <3 days ago)"""


# Output format templates for different analysis types
FULL_ANALYSIS_OUTPUT_FORMAT = """Provide your analysis in this structure:

### 📊 Executive Summary
[2-3 sentences on overall marketing health and key insight]

---

## 🔍 PART 1: WHAT HAPPENED (Status Updates on Past Changes)

For each past change that has 3d/7d/14d/30d data available:

**[Change Description] - [Timeframe] Assessment**
- Impact Verdict: [STRONG POSITIVE / POSITIVE / NEUTRAL / SLIGHTLY NEGATIVE / NEGATIVE]
- Revenue: [direction] ([+X%])
- New Customers: [direction] ([+X%])
- Branded Search: [direction] ([+X%])
- Amazon Halo: [direction] ([+X%])
- Recommendation: [SCALE MORE / HOLD / REVERSE THE CHANGE / CONTINUE MONITORING]

If no past changes have data yet, note "No changes ready for follow-up yet."

---

## 🎯 PART 2: WHAT TO DO NOW (New Recommendations)

For each new recommendation:

**[ACTION]: [Campaign/Channel Name]**
- What: [Specific action with dollar amounts or percentages]
- Why: [Multi-signal reasoning - cite specific metrics]
- Confidence: [High/Medium/Low]
- Signals considered: [List which signals informed this]
- Risk: [What could go wrong]
- Monitor: [What to watch after implementing]

Note: Items in cooling off period (changed <3 days ago) should NOT receive new recommendations.

---

### Learning from Past Decisions
[If past recommendation data is provided, note any patterns or lessons]

### Questions/Uncertainties
[Any areas where you need more data or where the signals conflict]"""


QUICK_CHECK_OUTPUT_FORMAT = """This is a QUICK 3-DAY CHECK. Focus only on recent changes.

### 📊 Quick Summary
[1-2 sentences on how the week is going so far]

---

## 🔍 3-DAY IMPACT CHECK

For each change made on Monday (or recently) that now has 3 days of data:

**[Change Description]**
- 3-Day Verdict: [LOOKING GOOD / TOO EARLY / CONCERNING]
- Early signals: [Brief list of what's moving]
- Action: [CONTINUE / MONITOR CLOSELY / CONSIDER REVERTING if severely negative]

---

## ⚠️ Alerts (if any)
[Only call out if something is severely off-track and needs immediate attention]

Note: Full recommendations will come on Monday. This is just a health check."""


def build_synthesis_context(days: int = 30, analysis_type: str = "full") -> str:
    """
    Build comprehensive context for LLM synthesis.

    This gathers all available signals and formats them for the LLM.

    Args:
        days: Number of days to analyze
        analysis_type: "full" for Monday analysis, "quick" for Thursday check
    """
    lines = [
        "=" * 60,
        "MARKETING PERFORMANCE DATA FOR ANALYSIS",
        f"Generated: {datetime.now(EST).strftime('%Y-%m-%d %H:%M:%S')} EST",
        f"Analysis Type: {analysis_type.upper()}",
        "=" * 60,
        "",
    ]

    # 0. Funnel Impact Follow-ups (THE KEY SECTION)
    try:
        followup_summary = build_followup_summary_for_llm(analysis_type)
        if followup_summary and followup_summary != "No recent changes to follow up on.":
            lines.extend([
                "## CHANGE IMPACT FOLLOW-UPS (CRITICAL - Review Past Changes First)",
                "",
                followup_summary,
                "",
            ])
    except Exception as e:
        lines.append(f"(Funnel impact tracking unavailable: {e})")
        lines.append("")

    # 0b. Cooling Off Items
    try:
        cooling_off = get_items_in_cooling_off()
        if cooling_off.get("channels") or cooling_off.get("campaigns"):
            lines.extend([
                "## COOLING OFF PERIOD (Do NOT recommend changes to these)",
                "",
                f"Items changed in the last {COOLING_OFF_DAYS} days - let them run before adjusting:",
            ])
            for entry in cooling_off.get("entries", [])[:5]:
                lines.append(f"  - {entry['date']}: {entry['description']} ({entry['channel']})")
            lines.append("")
    except Exception:
        pass

    # 0c. Current Funnel Health Snapshot
    try:
        funnel_health = get_funnel_health_snapshot()
        if funnel_health.get("current_metrics"):
            assessment = funnel_health.get("health_assessment", {})
            lines.extend([
                "## CURRENT FUNNEL HEALTH (Last 7 Days)",
                "",
                f"Overall Verdict: {assessment.get('verdict', 'unknown').upper().replace('_', ' ')}",
                f"Score: {assessment.get('score', 0):.1f}",
                f"Signals: {', '.join(assessment.get('signals', []))}",
                "",
            ])
    except Exception:
        pass

    # 0d. Signal Predictiveness Analysis (Correlation Learning)
    try:
        correlation_insights = get_correlation_insights_for_llm()
        if correlation_insights and "not available" not in correlation_insights.lower():
            lines.extend([
                correlation_insights,
                "",
            ])
    except Exception:
        pass

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

    # 4. Multi-Signal Campaign Analysis (with new trend + confidence data)
    budget_warnings = []
    try:
        lines.append("## META ADS MULTI-SIGNAL ANALYSIS")
        lines.append("")

        # Get full data for enhanced context
        meta_data = get_multi_signal_campaign_view("facebook", days)

        # Add timeframe info
        timeframes = meta_data.get("timeframes_available", [])
        if len(timeframes) > 1:
            lines.append(f"*Timeframes available: {', '.join(timeframes)} - using trend comparison*")
            lines.append("")

        # Add budget concentration warnings
        meta_warnings = meta_data.get("budget_concentration_warnings", [])
        if meta_warnings:
            lines.append("**BUDGET CONCENTRATION ALERTS:**")
            for warn in meta_warnings:
                lines.append(f"  ⚠️ {warn['campaign_name']}: {warn['recommendation']}")
            lines.append("")
            budget_warnings.extend(meta_warnings)

        # Generate text context
        meta_analysis = get_campaign_for_llm_context("facebook", days)
        lines.append(meta_analysis)
        lines.append("")
    except Exception as e:
        lines.append(f"(Meta analysis unavailable: {e})")
        lines.append("")

    try:
        lines.append("## GOOGLE ADS MULTI-SIGNAL ANALYSIS")
        lines.append("")

        # Get full data for enhanced context
        google_data = get_multi_signal_campaign_view("google", days)

        # Add budget concentration warnings
        google_warnings = google_data.get("budget_concentration_warnings", [])
        if google_warnings:
            lines.append("**BUDGET CONCENTRATION ALERTS:**")
            for warn in google_warnings:
                lines.append(f"  ⚠️ {warn['campaign_name']}: {warn['recommendation']}")
            lines.append("")
            budget_warnings.extend(google_warnings)

        google_analysis = get_campaign_for_llm_context("google", days)
        lines.append(google_analysis)
        lines.append("")
    except Exception as e:
        lines.append(f"(Google analysis unavailable: {e})")
        lines.append("")

    # TikTok Ads Analysis (for halo effect analysis)
    try:
        lines.append("## TIKTOK ADS MULTI-SIGNAL ANALYSIS")
        lines.append("")
        lines.append("NOTE: TikTok is a discovery platform - expect strong HALO EFFECTS on:")
        lines.append("- Branded search volume (people see TikTok, then Google the brand)")
        lines.append("- Direct website traffic")
        lines.append("- Amazon sales")
        lines.append("Measure TikTok by correlation with these metrics, not just direct ROAS.")
        lines.append("")

        tiktok_analysis = get_campaign_for_llm_context("tiktok", days)
        if tiktok_analysis and "No campaigns" not in tiktok_analysis:
            lines.append(tiktok_analysis)
        else:
            lines.append("(TikTok data not yet available - recently started or no spend)")
        lines.append("")
    except Exception as e:
        lines.append(f"(TikTok analysis unavailable: {e})")
        lines.append("")

    # 4b. Summary of Budget Concentration Issues
    if budget_warnings:
        lines.append("## CBO BUDGET CONCENTRATION SUMMARY")
        lines.append("")
        lines.append(f"Found {len(budget_warnings)} campaign(s) with budget concentration concerns:")
        for warn in budget_warnings:
            best_text = "(best performer)" if warn.get("is_best_performer") else "(NOT best performer - action needed)"
            lines.append(f"  - {warn['campaign_name']}: {warn['top_adset_share']:.0f}% to '{warn['top_adset']}' {best_text}")
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


def _build_system_prompt(analysis_type: str) -> str:
    """
    Build the system prompt based on analysis type.

    Args:
        analysis_type: "full" for Monday analysis, "quick" for Thursday check
    """
    if analysis_type == "quick":
        type_name = "QUICK CHECK (Thursday)"
        type_desc = """QUICK 3-DAY CHECK. This runs mid-week to assess how Monday's changes are performing.
Focus on:
- 3-day impact of recent changes
- Any urgent issues that need immediate attention
- Quick pulse on overall funnel health

Do NOT make major new recommendations - save those for Monday's full analysis."""
        output_format = QUICK_CHECK_OUTPUT_FORMAT
    else:
        type_name = "FULL ANALYSIS (Monday)"
        type_desc = """FULL WEEKLY ANALYSIS. This is the main analysis that runs on Monday morning.
You will:
1. First, assess the IMPACT of past changes (3d/7d/14d/30d follow-ups)
2. Then, make NEW RECOMMENDATIONS based on current data
3. Learn from what worked and what didn't

This is continuous optimization - every week you make new decisions while tracking past ones."""
        output_format = FULL_ANALYSIS_OUTPUT_FORMAT

    return SYNTHESIS_SYSTEM_PROMPT.replace(
        "{{ANALYSIS_TYPE}}", type_name
    ).replace(
        "{{ANALYSIS_TYPE_DESCRIPTION}}", type_desc
    ).replace(
        "{{OUTPUT_FORMAT}}", output_format
    )


async def generate_synthesis(
    user_question: Optional[str] = None,
    days: int = 30,
    save_recommendations: bool = True,
    analysis_type: str = "full",
) -> dict:
    """
    Generate AI synthesis of marketing performance with recommendations.

    Args:
        user_question: Optional specific question to answer
        days: Number of days to analyze
        save_recommendations: Whether to save generated recommendations for tracking
        analysis_type: "full" for Monday analysis, "quick" for Thursday check

    Returns:
        Dictionary with synthesis results
    """
    if not ANTHROPIC_AVAILABLE:
        return {"error": "Anthropic library not installed"}

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    # Validate analysis type
    if analysis_type not in ["full", "quick"]:
        analysis_type = "full"

    # Build context
    context = build_synthesis_context(days, analysis_type)

    # Build appropriate system prompt
    system_prompt = _build_system_prompt(analysis_type)

    # Build the user message based on analysis type
    if user_question:
        user_message = f"""Here is the current marketing data and performance metrics:

{context}

---

Based on this data, please answer my question:

{user_question}

Provide your analysis following the output format in your instructions."""
    elif analysis_type == "quick":
        user_message = f"""Here is the current marketing data and performance metrics:

{context}

---

This is a QUICK MID-WEEK CHECK.

Focus on:
1. How are the changes made on Monday performing? (3-day impact)
2. Are there any urgent issues that need immediate attention?
3. Is the overall funnel healthy?

Keep it concise - major recommendations will wait for Monday's full analysis."""
    else:
        user_message = f"""Here is the current marketing data and performance metrics:

{context}

---

Please provide a comprehensive analysis.
Follow the output format in your instructions.

PART 1 - WHAT HAPPENED (Status Updates):
1. Review each past change that has data available (3d/7d/14d/30d)
2. Assess whether each change had a positive or negative FUNNEL IMPACT
3. Recommend whether to scale more, hold, or reverse each change

PART 2 - WHAT TO DO NOW (New Recommendations):
1. What are the top 3-5 NEW actions to take?
2. Which campaigns should be scaled, maintained, or cut?
3. How is TOF performing and should we adjust it?
4. Are there any concerning trends we need to address?
5. What learnings from past recommendations should inform our decisions?

REMEMBER:
- Items in cooling off period (<3 days since change) should NOT receive new recommendations
- Funnel impact > single platform ROAS
- 3d/7d are for ACTION, 14d/30d are for VALIDATION"""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
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

        usage_info = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        # Save to analysis history
        history_entry = save_to_history(
            synthesis=synthesis_text,
            recommendations_extracted=recommendations_extracted,
            question=user_question,
            days=days,
            usage=usage_info,
        )

        return {
            "success": True,
            "synthesis": synthesis_text,
            "recommendations_extracted": recommendations_extracted,
            "recommendations_saved": len(saved_recommendations),
            "context_summary": {
                "days_analyzed": days,
                "context_length": len(context),
                "analysis_type": analysis_type,
            },
            "usage": usage_info,
            "generated_at": datetime.now(EST).isoformat(),
            "history_id": history_entry.get("id"),
            "analysis_type": analysis_type,
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
