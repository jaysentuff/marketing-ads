"""
AI Synthesis API endpoints.

Provides the autonomous marketing optimization system powered by Claude.
This is the "brain" that reasons over all signals and generates
nuanced recommendations with full reasoning.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.ai_synthesis import (
    generate_synthesis,
    get_synthesis_status,
    build_synthesis_context,
)
from services.analysis_history import (
    get_history,
    get_analysis_by_id,
    delete_analysis,
)
from services.funnel_impact import (
    get_all_change_impacts,
    get_items_in_cooling_off,
    get_changes_needing_followup,
    get_funnel_health_snapshot,
    analyze_signal_predictiveness,
)
from services.multi_signal import (
    get_multi_signal_campaign_view,
    get_cross_channel_correlation,
)
from services.recommendations import (
    get_recent_recommendations,
    get_pending_recommendations,
    update_recommendation_status,
    get_recommendation_summary_for_llm,
    get_recommendations_needing_outcome_check,
    record_outcome,
    link_changelog_to_recommendation,
)
from services.data_loader import get_spend_outcome_correlation

router = APIRouter()


class SynthesisRequest(BaseModel):
    """Request for AI synthesis."""
    question: Optional[str] = None
    days: int = 30
    save_recommendations: bool = True
    analysis_type: str = "full"  # "full" for Monday, "quick" for Thursday


class UpdateRecommendationRequest(BaseModel):
    """Request to update a recommendation's status."""
    status: str  # pending, done, ignored, partial
    action_taken: Optional[str] = None
    reason_not_followed: Optional[str] = None


class LinkChangelogRequest(BaseModel):
    """Request to link a changelog entry to a recommendation."""
    changelog_entry_id: int


# =============================================================================
# AI Synthesis Endpoints
# =============================================================================

@router.get("/status")
async def get_status():
    """Check if AI synthesis is available."""
    return get_synthesis_status()


@router.post("/analyze")
async def analyze(request: SynthesisRequest):
    """
    Generate comprehensive AI analysis with recommendations.

    This is the main endpoint that:
    1. Gathers all available signals (multi-source)
    2. Includes past recommendations and outcomes (feedback loop)
    3. Calls Claude to reason over everything
    4. Returns synthesis with actionable recommendations

    Analysis types:
    - "full" (default): Full Monday analysis with change follow-ups + new recommendations
    - "quick": Thursday quick check on recent changes (3-day impact)
    """
    result = await generate_synthesis(
        user_question=request.question,
        days=request.days,
        save_recommendations=request.save_recommendations,
        analysis_type=request.analysis_type,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/context")
async def get_context(days: int = 30, analysis_type: str = "full"):
    """
    Get the raw context that would be sent to the LLM.

    Useful for debugging and understanding what data the AI sees.
    """
    context = build_synthesis_context(days, analysis_type)
    return {
        "context": context,
        "length": len(context),
        "days": days,
        "analysis_type": analysis_type,
    }


# =============================================================================
# Funnel Impact Tracking Endpoints
# =============================================================================

@router.get("/funnel-impact")
async def get_funnel_impact(days: int = 30):
    """
    Get funnel impact data for all recent changes.

    Shows how each change affected the full funnel:
    - Revenue, orders, new customers
    - Branded search, Amazon halo
    - Multi-timeframe assessment (3d, 7d, 14d, 30d)
    """
    impacts = get_all_change_impacts(days)
    return {
        "impacts": impacts,
        "count": len(impacts),
    }


@router.get("/funnel-impact/health")
async def get_funnel_health():
    """
    Get current funnel health snapshot.

    Shows week-over-week funnel performance.
    """
    return get_funnel_health_snapshot()


@router.get("/funnel-impact/cooling-off")
async def get_cooling_off_items():
    """
    Get items currently in cooling off period.

    These items were changed in the last 3 days and should
    not receive new recommendations yet.
    """
    return get_items_in_cooling_off()


@router.get("/funnel-impact/followups")
async def get_followups(analysis_type: str = "full"):
    """
    Get changes that need follow-up based on analysis type.

    Returns:
    - action_ready: Changes with 3d/7d data ready for scaling decisions
    - validation_ready: Changes with 14d/30d data for strategy validation
    - pending: Changes still waiting for enough data
    """
    return get_changes_needing_followup(analysis_type)


# =============================================================================
# Multi-Signal Analysis Endpoints
# =============================================================================

@router.get("/campaigns/{platform}")
async def get_campaign_analysis(
    platform: str,
    days: int = 30,
    min_spend: float = 50.0,
    level: str = "campaign"
):
    """
    Get multi-signal analysis for campaigns on a platform.

    Returns each campaign with:
    - Platform ROAS (what Meta/Google report)
    - Kendall Last-Click ROAS (de-duplicated)
    - Kendall First-Click ROAS (awareness credit)
    - Session quality score (behavioral signals)
    - Weighted composite score
    - Attribution gap (how much platform over-claims)
    - Funnel role classification
    """
    if platform not in ["facebook", "google"]:
        raise HTTPException(status_code=400, detail="Platform must be 'facebook' or 'google'")

    if level not in ["campaign", "adset", "ad"]:
        level = "campaign"

    return get_multi_signal_campaign_view(platform, days, min_spend, level)


@router.get("/correlation/cross-channel")
async def get_channel_correlation_analysis(days: int = 30):
    """
    Get cross-channel correlation analysis.

    Answers: "Is Meta TOF creating demand that Google harvests?"

    Returns correlations between:
    - Meta spend and Google branded search (with lag analysis)
    - Meta spend and Google first-click revenue (with lag analysis)
    """
    result = get_cross_channel_correlation(days)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/correlation/spend-outcome")
async def get_spend_outcome_analysis(days: int = 14):
    """
    Get spend-to-outcome correlation analysis.

    Answers: "When spend changed, did outcomes follow?"

    Returns signal agreement analysis showing whether
    revenue, new customers, and branded search moved
    in the same direction as spend.
    """
    result = get_spend_outcome_correlation(days)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/correlation/signal-predictiveness")
async def get_signal_predictiveness(days: int = 60):
    """
    Analyze which signals actually predict revenue.

    Answers: "Does branded search predict revenue? Does Amazon?"

    Tests correlations between leading indicators and revenue:
    - Branded search → Revenue (with various lag periods)
    - Amazon sales → Shopify revenue
    - New customers → Revenue
    - Meta spend → Revenue

    Returns:
    - Correlation strengths for each signal
    - Best predictive lag period for each signal
    - Weight adjustment suggestions based on observed predictiveness

    This helps validate whether current weights are appropriate
    and informs future weight calibration.
    """
    result = analyze_signal_predictiveness(days)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# =============================================================================
# Recommendation Tracking Endpoints
# =============================================================================

@router.get("/recommendations")
async def list_recommendations(days: int = 30, limit: int = 50):
    """
    Get recent AI recommendations with their outcomes.

    This shows the history of what the AI recommended,
    what was acted upon, and what the outcomes were.
    """
    recommendations = get_recent_recommendations(days=days, limit=limit)
    return {
        "recommendations": recommendations,
        "count": len(recommendations),
    }


@router.get("/recommendations/pending")
async def list_pending_recommendations(days: int = 7):
    """
    Get recommendations that haven't been acted on yet.
    """
    pending = get_pending_recommendations(days=days)
    return {
        "recommendations": pending,
        "count": len(pending),
    }


@router.get("/recommendations/summary")
async def get_recommendations_summary(days: int = 30):
    """
    Get a summary of recommendation patterns and outcomes.

    This is what the AI uses to learn from past decisions.
    """
    return get_recommendation_summary_for_llm(days=days)


@router.put("/recommendations/{recommendation_id}/status")
async def update_status(recommendation_id: str, request: UpdateRecommendationRequest):
    """
    Update the status of a recommendation.

    Call this when:
    - User acts on a recommendation (status='done')
    - User ignores a recommendation (status='ignored', include reason_not_followed)
    - User partially implements (status='partial')
    """
    if request.status not in ["pending", "done", "ignored", "partial"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = update_recommendation_status(
        recommendation_id=recommendation_id,
        status=request.status,
        action_taken=request.action_taken,
        reason_not_followed=request.reason_not_followed,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return {"success": True, "recommendation": result}


@router.post("/recommendations/{recommendation_id}/link-changelog")
async def link_to_changelog(recommendation_id: str, request: LinkChangelogRequest):
    """
    Link a changelog entry to a recommendation.

    This creates the connection between what the AI recommended
    and what action was recorded in the activity log.
    """
    success = link_changelog_to_recommendation(
        changelog_entry_id=request.changelog_entry_id,
        recommendation_id=recommendation_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return {"success": True}


@router.get("/recommendations/needs-outcome-check")
async def get_recommendations_for_outcome_check():
    """
    Get recommendations that need outcome measurement.

    These are recommendations that were acted upon 7+ days ago
    but don't yet have outcome metrics recorded.

    A scheduled job should call this and then record_outcome
    for each recommendation.
    """
    return {
        "recommendations": get_recommendations_needing_outcome_check()
    }


# =============================================================================
# Analysis History Endpoints
# =============================================================================

@router.get("/history")
async def list_analysis_history(limit: int = 20, offset: int = 0):
    """
    Get analysis history.

    Returns a list of past analyses with timestamps, summaries,
    and recommendation counts for quick browsing.
    """
    return get_history(limit=limit, offset=offset)


@router.get("/history/{entry_id}")
async def get_analysis_detail(entry_id: str):
    """
    Get a specific analysis by ID.

    Returns the full analysis including synthesis text
    and all recommendations.
    """
    entry = get_analysis_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return entry


@router.delete("/history/{entry_id}")
async def delete_analysis_entry(entry_id: str):
    """
    Delete an analysis from history.
    """
    success = delete_analysis(entry_id)

    if not success:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {"success": True}


@router.post("/recommendations/{recommendation_id}/record-outcome")
async def record_recommendation_outcome(
    recommendation_id: str,
    days_after: int = 7,
):
    """
    Record the outcome metrics for a recommendation.

    This captures the metrics N days after the recommendation was acted upon,
    enabling the feedback loop that helps the AI learn.
    """
    # Get current metrics
    from services.data_loader import get_latest_report
    from services.data_loader import get_spend_outcome_correlation

    report = get_latest_report()
    summary = report.get("report", {}).get("summary", {}) if report else {}

    correlation = get_spend_outcome_correlation(days=7)
    efficiency = correlation.get("efficiency", {}) if "error" not in correlation else {}

    metrics_after = {
        "cam_per_order": summary.get("blended_cam_per_order", 0),
        "mer": efficiency.get("current_mer", 0),
        "ncac": efficiency.get("current_ncac", 0),
        "total_spend": summary.get("total_ad_spend", 0),
        "total_revenue": summary.get("total_revenue", 0),
    }

    result = record_outcome(
        recommendation_id=recommendation_id,
        metrics_after=metrics_after,
        days_after=days_after,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return {"success": True, "recommendation": result}
