"""
Changelog API endpoints.

Provides access to the activity log/changelog.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.changelog import (
    load_changelog,
    add_entry,
    get_recent_entries,
    get_entries_summary,
    delete_entry,
    update_entry,
    ACTION_TYPES,
)
from services.campaign_matcher import search_campaigns, get_all_campaigns

router = APIRouter()


class NewEntryRequest(BaseModel):
    """Request body for creating a new changelog entry."""
    action_type: str
    description: str
    channel: Optional[str] = None
    campaign: Optional[str] = None
    amount: Optional[float] = None
    percent_change: Optional[float] = None
    notes: Optional[str] = None
    metrics_snapshot: Optional[dict] = None
    timestamp: Optional[str] = None


class UpdateEntryRequest(BaseModel):
    """Request body for updating a changelog entry."""
    description: Optional[str] = None
    amount: Optional[float] = None
    percent_change: Optional[float] = None
    original_budget: Optional[float] = None
    notes: Optional[str] = None
    channel: Optional[str] = None
    campaign: Optional[str] = None
    timestamp: Optional[str] = None


@router.get("/entries")
async def get_entries(days: int = 30, limit: int = 50):
    """Get recent changelog entries."""
    entries = get_recent_entries(days=days, limit=limit)
    return {"entries": entries, "count": len(entries)}


@router.get("/all")
async def get_all_entries():
    """Get all changelog entries."""
    entries = load_changelog()
    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"entries": entries, "count": len(entries)}


@router.get("/summary")
async def get_summary():
    """Get text summary of recent changes (for AI context)."""
    return {"summary": get_entries_summary()}


@router.get("/action-types")
async def get_action_types():
    """Get available action types for the UI."""
    return {"action_types": [{"value": k, "label": v} for k, v in ACTION_TYPES]}


@router.post("/entries")
async def create_entry(request: NewEntryRequest):
    """Create a new changelog entry."""
    entry = add_entry(
        action_type=request.action_type,
        description=request.description,
        channel=request.channel,
        campaign=request.campaign,
        amount=request.amount,
        percent_change=request.percent_change,
        notes=request.notes,
        metrics_snapshot=request.metrics_snapshot,
        timestamp=request.timestamp,
    )
    return {"success": True, "entry": entry}


@router.put("/entries/{entry_id}")
async def edit_entry(entry_id: int, request: UpdateEntryRequest):
    """Update a changelog entry."""
    updated = update_entry(
        entry_id=entry_id,
        description=request.description,
        amount=request.amount,
        percent_change=request.percent_change,
        original_budget=request.original_budget,
        notes=request.notes,
        channel=request.channel,
        campaign=request.campaign,
        timestamp=request.timestamp,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    return {"success": True, "entry": updated}


@router.delete("/entries/{entry_id}")
async def remove_entry(entry_id: int):
    """Delete a changelog entry."""
    success = delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    return {"success": True, "deleted_id": entry_id}


@router.get("/campaigns/search")
async def search_campaign_names(
    q: str,
    channel: Optional[str] = None,
    limit: int = 10,
):
    """
    Search for campaign names with fuzzy matching.

    Use this for autocomplete when entering changelog entries.
    """
    if len(q) < 2:
        return {"campaigns": [], "query": q}

    results = search_campaigns(q, channel=channel, limit=limit)
    return {"campaigns": results, "query": q}


@router.get("/campaigns/all")
async def list_all_campaigns(channel: Optional[str] = None):
    """Get all unique campaign names from Meta and Google Ads."""
    campaigns = get_all_campaigns()
    if channel:
        campaigns = [c for c in campaigns if c["channel"].lower() == channel.lower()]
    return {"campaigns": campaigns, "count": len(campaigns)}
