"""
AI Chat API endpoints.

Provides Claude-powered marketing assistant functionality.
Includes chat history persistence for revisiting conversations.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / "connectors" / ".env")

from services.data_loader import (
    get_latest_report,
    get_decision_signals,
    get_blended_metrics,
    get_timeframe_summary,
)
from services.changelog import get_entries_summary
from services.chat_history import (
    get_all_sessions,
    get_session,
    create_session,
    update_session,
    delete_session,
)

router = APIRouter()

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


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

    tof = signals.get("tof_assessment")
    if tof:
        lines.extend([
            "",
            "--- TOF (Top-of-Funnel) Assessment ---",
            "NOTE: TOF campaigns should NOT be judged by direct ROAS.",
            f"Meta First-Click (7d): ${tof.get('meta_first_click_7d', 0):,.2f}",
            f"Blended NCAC: ${tof.get('ncac_7d_avg', 0):.2f} (Target: <$50)",
            f"Branded Search %: {tof.get('branded_search_pct', 0):.1f}%",
            f"Amazon Sales (7d): ${tof.get('amazon_sales_7d', 0):,.2f}",
            f"TOF Verdict: {tof.get('verdict', 'unknown')} - {tof.get('message', '')}",
        ])

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

    activity = get_entries_summary()
    lines.extend([
        "",
        "=== RECENT ACTIVITY LOG ===",
        activity,
    ])

    # Add short-term data for multiple timeframes (matches Short-Term Analysis page)
    lines.extend([
        "",
        "=== SHORT-TERM PERFORMANCE (Platform-Reported) ===",
        "NOTE: This is platform-reported data. Platform ROAS tends to over-attribute.",
        "Use Kendall attribution (30-day section above) for true multi-touch attribution.",
    ])

    for days in [1, 3, 7]:
        try:
            tf_data = get_timeframe_summary(days)
            tf_label = tf_data.get('timeframe', {}).get('label', f'{days} day(s)')
            lines.extend([
                "",
                f"--- {tf_label} ---",
                f"Revenue: ${tf_data['summary']['total_sales']:,.2f} | Orders: {tf_data['summary']['total_orders']} | Spend: ${tf_data['summary']['total_spend']:,.2f}",
                f"CAM/Order: ${tf_data['summary']['cam_per_order']:.2f} | Blended ROAS: {tf_data['summary']['blended_roas']:.2f}x",
                f"Google: ${tf_data['channels']['google']['spend']:,.2f} spend, {tf_data['channels']['google']['roas']:.2f}x ROAS",
                f"Meta: ${tf_data['channels']['meta']['spend']:,.2f} spend, {tf_data['channels']['meta']['roas']:.2f}x ROAS",
            ])

            # Only show campaign breakdown for yesterday (1-day) to keep it concise
            if days == 1:
                meta_camps = tf_data.get("meta_campaigns", [])
                if meta_camps:
                    lines.append("")
                    lines.append("Meta Campaigns (Yesterday):")
                    for camp in meta_camps[:8]:
                        lines.append(f"  {camp['name'][:45]}: ${camp.get('spend', 0):.2f} spend, {camp.get('roas', 0):.2f}x ROAS")

                google_camps = tf_data.get("google_campaigns", [])
                if google_camps:
                    lines.append("")
                    lines.append("Google Campaigns (Yesterday):")
                    for camp in google_camps[:8]:
                        lines.append(f"  {camp['name'][:45]}: ${camp.get('spend', 0):.2f} spend, {camp.get('roas', 0):.2f}x ROAS")

        except Exception as e:
            lines.append(f"({days}-day data unavailable: {e})")

    return "\n".join(lines)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    include_context: bool = True


class QuickQuestionRequest(BaseModel):
    question: str


@router.get("/status")
async def get_status():
    """Check if AI chat is available."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "available": ANTHROPIC_AVAILABLE and bool(api_key),
        "anthropic_installed": ANTHROPIC_AVAILABLE,
        "api_key_set": bool(api_key),
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a chat message and get AI response."""
    if not ANTHROPIC_AVAILABLE:
        raise HTTPException(status_code=503, detail="Anthropic library not installed")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="ANTHROPIC_API_KEY not configured")

    # Build messages
    messages = []

    if request.include_context and request.messages:
        context = get_marketing_context()
        first_message = request.messages[0]

        if len(request.messages) == 1:
            messages.append({
                "role": "user",
                "content": f"Here is my current marketing data:\n\n{context}\n\n---\n\nMy question: {first_message.content}"
            })
        else:
            for msg in request.messages[:-1]:
                messages.append({"role": msg.role, "content": msg.content})

            last_message = request.messages[-1]
            messages.append({
                "role": "user",
                "content": f"[Updated data context]\n{context}\n\n---\n\n{last_message.content}"
            })
    else:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages
        )

        return {
            "success": True,
            "message": response.content[0].text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        }

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-questions")
async def get_quick_questions():
    """Get list of quick question suggestions."""
    return {
        "questions": [
            {
                "id": "today",
                "label": "What should I do today?",
                "question": "Based on the current data, what are the top 3 actions I should take today to improve marketing performance?"
            },
            {
                "id": "tof",
                "label": "How is TOF performing?",
                "question": "How are my TOF (top-of-funnel) campaigns performing? Should I adjust the budget?"
            },
            {
                "id": "cam",
                "label": "Explain my CAM",
                "question": "Explain my current CAM (Contribution After Marketing) and what's driving it up or down."
            },
            {
                "id": "scale",
                "label": "What can I scale?",
                "question": "Which campaigns have the best performance and are ready to scale? What budget increase do you recommend?"
            },
        ]
    }


@router.get("/context")
async def get_context():
    """Get the current marketing context (for debugging)."""
    return {"context": get_marketing_context()}


# Chat History Endpoints

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    messages: list[ChatMessage]
    title: Optional[str] = None


@router.get("/sessions")
async def list_sessions():
    """Get all chat sessions."""
    sessions = get_all_sessions()
    return {"sessions": sessions}


@router.post("/sessions")
async def create_new_session(request: CreateSessionRequest):
    """Create a new chat session."""
    session = create_session(request.title)
    return {"success": True, "session": session}


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Get a specific chat session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


@router.put("/sessions/{session_id}")
async def update_chat_session(session_id: str, request: UpdateSessionRequest):
    """Update a chat session with new messages."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    session = update_session(session_id, messages, request.title)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session."""
    success = delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
