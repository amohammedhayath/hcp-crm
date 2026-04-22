"""
Chat endpoint – bridges the React UI ↔ LangGraph agent.
Also persists interactions that come via the chat channel.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.schemas.schemas import ChatRequest, ChatResponse
from app.agents.hcp_agent import run_agent
from app.models.models import Interaction, InteractionStatus, InteractionType

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def chat_message(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        result = await run_agent(
            user_message=payload.message,
            history=[m.model_dump() for m in payload.history],
            context=payload.context or {},
            db_session=db,
        )

        # Auto-persist if agent called log_interaction
        interaction_data = result.get("interaction_data")
        if result.get("tool_used") == "log_interaction" and interaction_data:
            try:
                date_str = interaction_data.get("date", datetime.utcnow().isoformat())
                parsed_date = datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                parsed_date = datetime.utcnow()

            raw_type = interaction_data.get("interaction_type", "phone").lower().replace(" ", "_")
            try:
                itype = InteractionType(raw_type)
            except ValueError:
                itype = InteractionType.phone

            obj = Interaction(
                hcp_id=interaction_data.get("hcp_id", payload.context.get("hcp_id", 1)),
                rep_id="rep_001",
                interaction_type=itype,
                date=parsed_date,
                duration_minutes=interaction_data.get("duration_minutes"),
                location=interaction_data.get("location"),
                notes=interaction_data.get("notes", ""),
                ai_summary=interaction_data.get("summary"),
                products_discussed=interaction_data.get("products_discussed", []),
                key_topics=interaction_data.get("key_topics", []),
                objections_raised=interaction_data.get("objections_raised", []),
                next_steps=interaction_data.get("next_steps", []),
                sentiment=interaction_data.get("sentiment"),
                status=InteractionStatus.logged,
                source="chat",
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
            result["interaction_data"]["db_id"] = obj.id

        # Auto-update if agent called schedule_follow_up
        if result.get("tool_used") == "schedule_follow_up" and interaction_data:
            interaction_id = interaction_data.get("interaction_id")
            if interaction_id:
                obj = db.query(Interaction).filter(Interaction.id == interaction_id).first()
                if obj:
                    try:
                        obj.follow_up_date = datetime.fromisoformat(
                            interaction_data.get("follow_up_date", "")
                        )
                    except (ValueError, TypeError):
                        pass
                    obj.follow_up_notes = interaction_data.get("follow_up_notes", "")
                    db.commit()

        # Auto-update if agent called edit_interaction
        if result.get("tool_used") == "edit_interaction" and interaction_data:
            interaction_id = interaction_data.get("interaction_id")
            field = interaction_data.get("field")
            new_value = interaction_data.get("new_value")
            if interaction_id and field and new_value is not None:
                obj = db.query(Interaction).filter(Interaction.id == interaction_id).first()
                if obj and hasattr(obj, field):
                    setattr(obj, field, new_value)
                    db.commit()

        return ChatResponse(
            session_id=payload.session_id,
            reply=result["reply"],
            tool_used=result.get("tool_used"),
            interaction_data=result.get("interaction_data"),
            action_taken=result.get("tool_used"),
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
