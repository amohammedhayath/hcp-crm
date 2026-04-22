"""
AI-First CRM – HCP Module
FastAPI entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import interactions, chat, hcps
from app.core.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI-First CRM – HCP Module",
    description="Healthcare Professional interaction management with LangGraph AI Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hcps.router, prefix="/api/hcps", tags=["HCPs"])
app.include_router(interactions.router, prefix="/api/interactions", tags=["Interactions"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI Chat"])


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "HCP CRM API"}
