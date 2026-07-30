"""
app/db/models.py

SQLAlchemy Models for Learning Agent.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class LearningPlan(Base):
    __tablename__ = "learning_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    career_goal = Column(String(255), nullable=False)
    current_level = Column(String(100), nullable=True)
    missing_skills = Column(JSON, nullable=True)
    learning_roadmap = Column(JSON, nullable=True)
    recommended_topics = Column(JSON, nullable=True)
    practice_recommendations = Column(JSON, nullable=True)
    recommended_certifications = Column(JSON, nullable=True)
    daily_plan = Column(JSON, nullable=True)
    weekly_schedule = Column(JSON, nullable=True)
    next_milestone = Column(Text, nullable=True)
    motivation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LearningProgress(Base):
    __tablename__ = "learning_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(String(255), nullable=False)
    completed_count = Column(Integer, default=0)
    remaining_count = Column(Integer, default=0)
    percentage = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), nullable=True)
    title = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    difficulty = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LearningHistory(Base):
    __tablename__ = "learning_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    career_goal = Column(String(255), nullable=False)
    status = Column(String(50), default="Active")
    progress_percentage = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(100), default="Learning Agent")
    action = Column(String(255), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
