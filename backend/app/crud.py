from sqlalchemy.orm import Session
from . import models

def get_bug_report(db: Session, bug_report_id: int):
    return db.query(models.BugReport).filter(models.BugReport.id == bug_report_id).first()

def get_bug_reports(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.BugReport).offset(skip).limit(limit).all()

def create_bug_report(db: Session, description: str):
    db_bug_report = models.BugReport(description=description)
    db.add(db_bug_report)
    db.commit()
    db.refresh(db_bug_report)
    return db_bug_report

def update_bug_report_status(db: Session, bug_report_id: int, status: str):
    db_bug_report = db.query(models.BugReport).filter(models.BugReport.id == bug_report_id).first()
    if db_bug_report:
        db_bug_report.status = status
        db.commit()
        db.refresh(db_bug_report)
    return db_bug_report

def create_session(db: Session, session_id: str, bug_report_id: int):
    db_session = models.Session(id=session_id, bug_report_id=bug_report_id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_session(db: Session, session_id: str):
    return db.query(models.Session).filter(models.Session.id == session_id).first()

def update_session_usage(db: Session, session_id: str, prompt_tokens: int, completion_tokens: int, estimated_cost: float):
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if db_session:
        db_session.prompt_tokens += prompt_tokens
        db_session.completion_tokens += completion_tokens
        db_session.total_tokens = db_session.prompt_tokens + db_session.completion_tokens
        # Update cost (assuming estimated_cost is a float, we store it as string for precision or just format it)
        current_cost = float(db_session.estimated_cost)
        db_session.estimated_cost = f"{current_cost + estimated_cost:.6f}"
        db.commit()
        db.refresh(db_session)
    return db_session
