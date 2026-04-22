"""
LangGraph AI Agent for HCP CRM
─────────────────────────────
Tools:
  1. log_interaction      – capture & summarise a new HCP interaction
  2. edit_interaction     – modify fields of an existing interaction
  3. get_hcp_profile      – retrieve HCP info + interaction history
  4. schedule_follow_up   – set a follow-up task for a logged interaction
  5. analyze_sentiment    – run sentiment + objection analysis on notes
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.core.config import get_settings

settings = get_settings()

# ── LLM ──────────────────────────────────────────────────────────────────────

def _get_llm(tools=None):
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.primary_model,   # gemma2-9b-it
        temperature=0.2,
    )
    if tools:
        return llm.bind_tools(tools)
    return llm


# ── Agent State ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    db_session: Any          # SQLAlchemy session injected at runtime
    context: dict            # extra context (hcp_id, rep_id, etc.)
    tool_result: Optional[dict]
    last_tool: Optional[str]


# ── Tool implementations (stateless helpers) ─────────────────────────────────

def _summarise_notes(notes: str, llm: ChatGroq) -> dict:
    """Use LLM to extract structured data from free-text notes."""
    prompt = f"""You are a life-science CRM assistant.

Extract the following from the rep notes below and respond ONLY with valid JSON:
{{
  "summary": "<2-3 sentence summary>",
  "products_discussed": ["<product>"],
  "key_topics": ["<topic>"],
  "objections_raised": ["<objection>"],
  "next_steps": ["<action>"],
  "sentiment": "positive|neutral|negative"
}}

Notes:
{notes}
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```json\s*|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "summary": notes[:300],
            "products_discussed": [],
            "key_topics": [],
            "objections_raised": [],
            "next_steps": [],
            "sentiment": "neutral",
        }


# ── LangChain @tool definitions ───────────────────────────────────────────────

@tool
def log_interaction(
    hcp_id: int,
    interaction_type: str,
    date: str,
    notes: str,
    duration_minutes: Optional[int] = None,
    location: Optional[str] = None,
    products_discussed: Optional[list] = None,
) -> dict:
    """
    Log a new HCP interaction. The LLM will summarise the free-text notes and
    extract structured fields (products, topics, objections, next steps, sentiment).

    Args:
        hcp_id: Database ID of the HCP
        interaction_type: one of in_person|phone|email|virtual|conference
        date: ISO-8601 datetime string
        notes: Free-text representative notes about the interaction
        duration_minutes: How long the interaction lasted
        location: Where the interaction took place
        products_discussed: List of product names mentioned
    """
    # This tool is a schema descriptor; actual DB write happens in the node wrapper.
    return {
        "tool": "log_interaction",
        "hcp_id": hcp_id,
        "interaction_type": interaction_type,
        "date": date,
        "notes": notes,
        "duration_minutes": duration_minutes,
        "location": location,
        "products_discussed": products_discussed or [],
    }


@tool
def edit_interaction(
    interaction_id: int,
    field: str,
    new_value: str,
) -> dict:
    """
    Edit a specific field on an existing logged interaction.

    Args:
        interaction_id: The ID of the interaction to update
        field: The field name to update (e.g. 'notes', 'follow_up_date', 'status')
        new_value: The new value as a string (dates in ISO-8601 format)
    """
    return {
        "tool": "edit_interaction",
        "interaction_id": interaction_id,
        "field": field,
        "new_value": new_value,
    }


@tool
def get_hcp_profile(hcp_id: int) -> dict:
    """
    Retrieve detailed HCP profile including recent interactions and engagement history.

    Args:
        hcp_id: The database ID of the HCP
    """
    return {"tool": "get_hcp_profile", "hcp_id": hcp_id}


@tool
def schedule_follow_up(
    interaction_id: int,
    follow_up_date: str,
    follow_up_notes: str,
) -> dict:
    """
    Schedule a follow-up task linked to an existing interaction.

    Args:
        interaction_id: The interaction to attach the follow-up to
        follow_up_date: ISO-8601 date for the follow-up
        follow_up_notes: Description of what needs to be done
    """
    return {
        "tool": "schedule_follow_up",
        "interaction_id": interaction_id,
        "follow_up_date": follow_up_date,
        "follow_up_notes": follow_up_notes,
    }


@tool
def analyze_sentiment(interaction_id: int, notes: str) -> dict:
    """
    Run AI-powered sentiment and objection analysis on interaction notes.
    Returns sentiment classification (positive/neutral/negative), detected
    objections, and recommended next-best actions.

    Args:
        interaction_id: The interaction to analyse
        notes: The free-text notes to analyse
    """
    return {
        "tool": "analyze_sentiment",
        "interaction_id": interaction_id,
        "notes": notes,
    }


ALL_TOOLS = [log_interaction, edit_interaction, get_hcp_profile, schedule_follow_up, analyze_sentiment]
TOOL_NODE = ToolNode(ALL_TOOLS)


# ── Graph nodes ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent CRM assistant embedded in a life-science field
force application. You help pharmaceutical sales representatives log and manage their
interactions with Healthcare Professionals (HCPs).

You have access to these tools:
1. log_interaction   – create a new interaction record with AI-powered summarisation
2. edit_interaction  – update a specific field on an existing interaction
3. get_hcp_profile   – fetch HCP details and history
4. schedule_follow_up – attach a follow-up task to an interaction
5. analyze_sentiment  – analyse sentiment and objections in interaction notes

Always confirm actions clearly and be concise. If the user provides notes, extract
key clinical and commercial details before logging. When you detect an objection or
a follow-up commitment in the conversation, proactively offer to schedule it.

Today's date (UTC): {today}
"""


def agent_node(state: AgentState) -> AgentState:
    llm_with_tools = _get_llm(ALL_TOOLS)
    system = SYSTEM_PROMPT.format(today=datetime.utcnow().strftime("%Y-%m-%d"))
    messages = [SystemMessage(content=system)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response], "last_tool": None}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", TOOL_NODE)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


GRAPH = build_graph()


# ── Public interface ──────────────────────────────────────────────────────────

async def run_agent(
    user_message: str,
    history: list[dict],
    context: dict,
    db_session,
) -> dict:
    """
    Entry point for the chat API.
    Returns {"reply": str, "tool_used": str | None, "interaction_data": dict | None}
    """
    # Convert history dicts → LangChain messages
    lc_messages = []
    for m in history:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        else:
            lc_messages.append(AIMessage(content=m["content"]))
    lc_messages.append(HumanMessage(content=user_message))

    initial_state: AgentState = {
        "messages": lc_messages,
        "db_session": db_session,
        "context": context,
        "tool_result": None,
        "last_tool": None,
    }

    final_state = await GRAPH.ainvoke(initial_state)

    # Extract reply and tool information
    last_msg = final_state["messages"][-1]
    reply = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    # Detect which tool (if any) was called
    tool_used = None
    interaction_data = None
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                tool_used = data.get("tool")
                interaction_data = data
            except Exception:
                pass
            break

    # If log_interaction was called, enrich with LLM summarisation
    if tool_used == "log_interaction" and interaction_data:
        llm = _get_llm()
        enriched = _summarise_notes(interaction_data.get("notes", ""), llm)
        interaction_data.update(enriched)

    if tool_used == "analyze_sentiment" and interaction_data:
        llm = _get_llm()
        enriched = _summarise_notes(interaction_data.get("notes", ""), llm)
        interaction_data.update(enriched)

    return {
        "reply": reply,
        "tool_used": tool_used,
        "interaction_data": interaction_data,
    }
