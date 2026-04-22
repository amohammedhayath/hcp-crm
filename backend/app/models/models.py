"""
ORM Models for HCP CRM
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class InteractionType(str, enum.Enum):
    in_person = "in_person"
    phone = "phone"
    email = "email"
    virtual = "virtual"
    conference = "conference"


class InteractionStatus(str, enum.Enum):
    draft = "draft"
    logged = "logged"
    reviewed = "reviewed"


class HCP(Base):
    __tablename__ = "hcps"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    specialty = Column(String(150))
    institution = Column(String(200))
    email = Column(String(200), unique=True, index=True)
    phone = Column(String(50))
    territory = Column(String(100))
    npi_number = Column(String(20), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interactions = relationship("Interaction", back_populates="hcp")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(100))
    description = Column(Text)


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    hcp_id = Column(Integer, ForeignKey("hcps.id"), nullable=False)
    rep_id = Column(String(100), default="rep_001")

    interaction_type = Column(SAEnum(InteractionType), nullable=False)
    status = Column(SAEnum(InteractionStatus), default=InteractionStatus.draft)

    date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer)
    location = Column(String(200))

    # Clinical / sales context
    products_discussed = Column(JSON, default=list)   # list of product names
    key_topics = Column(JSON, default=list)            # extracted topics
    objections_raised = Column(JSON, default=list)    # objections extracted
    next_steps = Column(JSON, default=list)           # follow-up items

    # Free-text fields
    notes = Column(Text)
    ai_summary = Column(Text)                          # LLM-generated summary
    sentiment = Column(String(50))                     # positive/neutral/negative

    # Follow-up
    follow_up_date = Column(DateTime)
    follow_up_notes = Column(Text)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = Column(String(50), default="form")  # "form" | "chat"

    hcp = relationship("HCP", back_populates="interactions")
