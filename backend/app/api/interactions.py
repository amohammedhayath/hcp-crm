from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.models import Interaction, HCP, InteractionStatus
from app.schemas.schemas import InteractionCreate, InteractionUpdate, InteractionResponse

router = APIRouter()


@router.get("/", response_model=List[InteractionResponse])
def list_interactions(
    hcp_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(Interaction)
    if hcp_id:
        q = q.filter(Interaction.hcp_id == hcp_id)
    return q.order_by(Interaction.date.desc()).offset(skip).limit(limit).all()


@router.get("/{interaction_id}", response_model=InteractionResponse)
def get_interaction(interaction_id: int, db: Session = Depends(get_db)):
    obj = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return obj


@router.post("/", response_model=InteractionResponse, status_code=201)
def create_interaction(payload: InteractionCreate, db: Session = Depends(get_db)):
    hcp = db.query(HCP).filter(HCP.id == payload.hcp_id).first()
    if not hcp:
        raise HTTPException(status_code=404, detail="HCP not found")

    interaction = Interaction(**payload.model_dump())
    interaction.status = InteractionStatus.logged
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


@router.patch("/{interaction_id}", response_model=InteractionResponse)
def update_interaction(
    interaction_id: int,
    payload: InteractionUpdate,
    db: Session = Depends(get_db),
):
    obj = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Interaction not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(obj, field, value)

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{interaction_id}", status_code=204)
def delete_interaction(interaction_id: int, db: Session = Depends(get_db)):
    obj = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Interaction not found")
    db.delete(obj)
    db.commit()
