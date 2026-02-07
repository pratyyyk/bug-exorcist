from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from typing import TYPE_CHECKING
from .database import Base

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

class BugReport(Base):
    __tablename__ = "bug_reports"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True)
    status = Column(String, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, index=True)
    bug_report_id = Column(Integer, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(String, default="0.00")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_approved = Column(Integer, default=0) # 0: pending, 1: approved, -1: rejected
    fixed_code = Column(Text, nullable=True)
    repo_path = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    referenced_files = Column(Text, nullable=True) # JSON list of files used for RAG context
