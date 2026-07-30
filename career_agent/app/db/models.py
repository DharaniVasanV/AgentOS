"""
app/db/models.py

ORM model for Career Agent (`career_analyses` table).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class CareerAnalysis(Base):
    __tablename__ = "career_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    input_type: Mapped[str] = mapped_column(String(100), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=True)
    career_summary: Mapped[str] = mapped_column(Text, nullable=True)
    
    ats_score: Mapped[int] = mapped_column(Integer, nullable=True)
    employability_score: Mapped[int] = mapped_column(Integer, nullable=True)
    
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
