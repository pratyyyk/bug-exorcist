import logging
import json
from sqlalchemy.orm import Session
from typing import Optional, List
from . import models

logger = logging.getLogger(__name__)

def get_bug_report(db: Session, bug_report_id: int) -> Optional[models.BugReport]:
    return db.query(models.BugReport).filter(models.BugReport.id == bug_report_id).first()

def get_bug_reports(db: Session, skip: int = 0, limit: int = 100) -> List[models.BugReport]:
    return db.query(models.BugReport).offset(skip).limit(limit).all()

def create_bug_report(db: Session, description: str) -> models.BugReport:
    db_bug_report = models.BugReport(description=description)
    db.add(db_bug_report)
    db.commit()
    db.refresh(db_bug_report)
    return db_bug_report

def update_bug_report_status(db: Session, bug_report_id: int, status: str) -> Optional[models.BugReport]:
    db_bug_report = db.query(models.BugReport).filter(models.BugReport.id == bug_report_id).first()
    if db_bug_report:
        try:
            db_bug_report.status = status
            db.commit()
            db.refresh(db_bug_report)
        except Exception as e:
            logger.error(f"Error updating bug report status for {bug_report_id}: {e}")
            db.rollback()
            return None
    return db_bug_report

def create_session(db: Session, session_id: str, bug_report_id: int):
    try:
        db_session = models.Session(id=session_id, bug_report_id=bug_report_id)
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session
    except Exception as e:
        logger.error(f"Error creating session {session_id}: {e}")
        db.rollback()
        return None

def get_session(db: Session, session_id: str):
    return db.query(models.Session).filter(models.Session.id == session_id).first()

def update_session_usage(db: Session, session_id: str, prompt_tokens: int, completion_tokens: int, estimated_cost: float):
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not db_session:
        logger.warning(f"Session {session_id} not found for usage update")
        return None
        
    try:
        db_session.prompt_tokens += prompt_tokens
        db_session.completion_tokens += completion_tokens
        db_session.total_tokens = db_session.prompt_tokens + db_session.completion_tokens
        
        # Robust cost parsing with fallback
        try:
            current_cost = float(db_session.estimated_cost or 0)
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse current cost '{db_session.estimated_cost}' for session {session_id}: {e}")
            current_cost = 0.0
            
        db_session.estimated_cost = f"{current_cost + estimated_cost:.6f}"
        db.commit()
        db.refresh(db_session)
        return db_session
    except Exception as e:
        logger.error(f"Error updating session usage for {session_id}: {e}")
        db.rollback()
        return None

def update_session_approval(db: Session, session_id: str, is_approved: int, fixed_code: str = None, repo_path: str = None, file_path: str = None):
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not db_session:
        return None
    try:
        db_session.is_approved = is_approved
        if fixed_code:
            db_session.fixed_code = fixed_code
        if repo_path:
            db_session.repo_path = repo_path
        if file_path:
            db_session.file_path = file_path
        db.commit()
        db.refresh(db_session)
        return db_session
    except Exception as e:
        logger.error(f"Error updating session approval for {session_id}: {e}")
        db.rollback()
        return None

def update_session_referenced_files(db: Session, session_id: str, files: List[str]):
    """Update the list of files referenced by the AI for this session."""
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not db_session:
        return None
    try:
        # Merge with existing files if any
        existing = json.loads(db_session.referenced_files) if db_session.referenced_files else []
        updated = list(set(existing + files))
        db_session.referenced_files = json.dumps(updated)
        db.commit()
        db.refresh(db_session)
        return db_session
    except Exception as e:
        logger.error(f"Error updating referenced files for {session_id}: {e}")
        db.rollback()
        return None
