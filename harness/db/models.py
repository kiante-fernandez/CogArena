from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
from pydantic import BaseModel


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)
    scaffold = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    observation_mode = Column(String, nullable=True)
    status = Column(String, nullable=False, default="created")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    task_results = relationship("TaskResult", back_populates="session")
    scores = relationship("Score", back_populates="session")


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    task_id = Column(String, nullable=False)
    trial_data = Column(Text, nullable=False)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="task_results")


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    task_id = Column(String, nullable=False)
    l1_completion = Column(Float, nullable=False)
    l2_accuracy = Column(Float, nullable=False)
    l3_behavioral = Column(Float, nullable=False)
    composite = Column(Float, nullable=False)
    details = Column(Text, nullable=True)
    scored_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="scores")


# Pydantic schemas

class SessionCreate(BaseModel):
    agent_name: str
    scaffold: str | None = None
    model_name: str | None = None
    observation_mode: str | None = None


class TaskInfo(BaseModel):
    task_id: str
    url: str


class SessionResponse(BaseModel):
    session_id: str
    tasks: list[TaskInfo]
    status: str


class TrialDataSubmission(BaseModel):
    trial_data: list[dict]
    metadata: dict | None = None


class TaskScore(BaseModel):
    task_id: str
    l1_completion: float
    l2_accuracy: float
    l3_behavioral: float
    composite: float
    details: dict | None = None


class ScorecardResponse(BaseModel):
    session_id: str
    task_scores: list[TaskScore]
    composite_score: float
    l1_overall: float
    l2_overall: float
    l3_overall: float
