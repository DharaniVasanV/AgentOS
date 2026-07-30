"""
app/db/models.py

ORM model for Research Agent (`research_analyses` table).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class ResearchAnalysis(Base):
    __tablename__ = "research_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    content_type: Mapped[str] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Store complete structured extraction result (all 19 steps) as JSON
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    sentiment: Mapped[str] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
