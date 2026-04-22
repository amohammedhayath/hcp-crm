"""
Pydantic v2 schemas for request / response validation
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator
from app.models.models import InteractionType, InteractionStatus


# ── HCP schemas ─────────────────────────────────────────────────────────────

class HCPBase(BaseModel):
    first_name: str
    last_name: str
    specialty: Optional[str] = None
    institution: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    territory: Optional[str] = None
    npi_number: Optional[str] = None


class HCPCreate(HCPBase):
    pass


class HCPResponse(HCPBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Interaction schemas ───────────────────────────────────────────────────────

class InteractionBase(BaseModel):
    hcp_id: int
    interaction_type: InteractionType
    date: datetime
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    products_discussed: Optional[List[str]] = []
    key_topics: Optional[List[str]] = []
    objections_raised: Optional[List[str]] = []
    next_steps: Optional[List[str]] = []
    notes: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    follow_up_notes: Optional[str] = None


class InteractionCreate(InteractionBase):
    source: str = "form"


class InteractionUpdate(BaseModel):
    interaction_type: Optional[InteractionType] = None
    date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    products_discussed: Optional[List[str]] = None
    key_topics: Optional[List[str]] = None
    objections_raised: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None
    notes: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    follow_up_notes: Optional[str] = None
    status: Optional[InteractionStatus] = None


class InteractionResponse(InteractionBase):
    id: int
    rep_id: str
    status: InteractionStatus
    ai_summary: Optional[str] = None
    sentiment: Optional[str] = None
    source: str
    created_at: datetime
    updated_at: datetime
    hcp: Optional[HCPResponse] = None

    model_config = {"from_attributes": True}


# ── Chat schemas ──────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: List[ChatMessage] = []
    context: Optional[dict] = {}


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    action_taken: Optional[str] = None
    interaction_data: Optional[dict] = None
    tool_used: Optional[str] = None
