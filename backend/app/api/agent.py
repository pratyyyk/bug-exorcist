"""
backend/app/api/agent.py - FastAPI endpoints for Bug Exorcist Agent

This module provides REST API endpoints to interact with the autonomous debugging agent.
Enhanced with automatic retry logic for failed fixes.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import os

from core.agent import BugExorcistAgent, quick_fix, fix_with_retry
from app.database import SessionLocal
from app import crud


router = APIRouter(prefix="/api/agent", tags=["agent"])


# Request/Response Models
class BugAnalysisRequest(BaseModel):
    """Request model for bug analysis"""
    error_message: str = Field(..., description="The error message with stack trace")
    code_snippet: str = Field(..., description="The code that caused the error")
    file_path: Optional[str] = Field(None, description="Path to the file containing the bug")
    additional_context: Optional[str] = Field(None, description="Additional context about the bug")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key (optional, uses env if not provided)")
    use_retry: bool = Field(True, description="Enable automatic retry logic (default: True)")
    max_attempts: int = Field(3, description="Maximum retry attempts (default: 3, max: 5)", ge=1, le=5)

    class Config:
        json_schema_extra = {
            "example": {
                "error_message": "ZeroDivisionError: division by zero\n  File 'calc.py', line 10",
                "code_snippet": "def divide(a, b):\n    return a / b",
                "file_path": "calc.py",
                "additional_context": "This function is called from the API endpoint",
                "use_retry": True,
                "max_attempts": 3
            }
        }


class BugAnalysisResponse(BaseModel):
    """Response model for bug analysis"""
    bug_id: str
    root_cause: str
    fixed_code: str
    explanation: str
    confidence: float
    original_error: str
    timestamp: str
    attempt_number: Optional[int] = 1
    usage: Optional[Dict[str, Any]] = None


class RetryFixRequest(BaseModel):
    """Request model for fix with retry logic"""
    error_message: str
    code_snippet: str
    file_path: Optional[str] = None
    additional_context: Optional[str] = None
    openai_api_key: Optional[str] = None
    max_attempts: int = Field(3, ge=1, le=5)


class RetryFixResponse(BaseModel):
    """Response model for retry fix"""
    success: bool
    final_fix: Optional[Dict[str, Any]]
    all_attempts: List[Dict[str, Any]]
    total_attempts: int
    message: str
    last_error: Optional[str] = None


class QuickFixRequest(BaseModel):
    """Request model for quick fix"""
    error: str
    code: str
    openai_api_key: Optional[str] = None


class QuickFixResponse(BaseModel):
    """Response model for quick fix"""
    fixed_code: str


# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/analyze", response_model=BugAnalysisResponse)
async def analyze_bug(request: BugAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze a bug and generate a fix using GPT-4o.
    
    This endpoint now supports automatic retry logic:
    - If use_retry=True (default), will automatically retry up to max_attempts times
    - Each retry learns from previous failures
    - Returns the first successful fix
    
    This endpoint:
    1. Creates a bug report in the database
    2. Analyzes the error using the Bug Exorcist agent
    3. Verifies the fix in sandbox
    4. Retries automatically if verification fails (up to max_attempts)
    5. Returns the working fix or details of all attempts
    
    Args:
        request: Bug analysis request with error details
        db: Database session
        
    Returns:
        Analysis results with fixed code (from successful attempt)
    """
    try:
        # Create bug report in database
        bug_report = crud.create_bug_report(
            db=db,
            description=f"{request.error_message[:200]}..."
        )
        bug_id = f"BUG-{bug_report.id}"
        
        # Create a session for tracking usage (using bug_id as session_id for now or random)
        import uuid
        session_id = str(uuid.uuid4())
        crud.create_session(db=db, session_id=session_id, bug_report_id=bug_report.id)
        
        # Get API key (from request or environment)
        api_key = request.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="OpenAI API key is required. Provide it in the request or set OPENAI_API_KEY environment variable."
            )
        
        # Initialize agent
        agent = BugExorcistAgent(bug_id=bug_id, openai_api_key=api_key)
        
        if request.use_retry:
            # Use retry logic
            retry_result = await agent.analyze_and_fix_with_retry(
                error_message=request.error_message,
                code_snippet=request.code_snippet,
                file_path=request.file_path,
                additional_context=request.additional_context,
                max_attempts=request.max_attempts
            )
            
            # Accumulate usage from all attempts
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_cost = 0.0
            
            for attempt in retry_result.get('all_attempts', []):
                fix_res = attempt.get('fix_result', {})
                usage = fix_res.get('usage', {})
                total_prompt_tokens += usage.get('prompt_tokens', 0)
                total_completion_tokens += usage.get('completion_tokens', 0)
                total_cost += usage.get('estimated_cost', 0.0)
            
            # Update session usage in DB
            crud.update_session_usage(
                db=db, 
                session_id=session_id, 
                prompt_tokens=total_prompt_tokens, 
                completion_tokens=total_completion_tokens, 
                estimated_cost=total_cost
            )
            
            # Update bug report status based on result
            if retry_result['success']:
                crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="fixed")
                final_fix = retry_result['final_fix']
                
                return BugAnalysisResponse(
                    bug_id=bug_id,
                    root_cause=final_fix['root_cause'],
                    fixed_code=final_fix['fixed_code'],
                    explanation=final_fix['explanation'],
                    confidence=final_fix['confidence'],
                    original_error=request.error_message,
                    timestamp=final_fix['timestamp'],
                    attempt_number=retry_result['total_attempts'],
                    usage={
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                        "estimated_cost": f"{total_cost:.6f}",
                        "session_id": session_id
                    }
                )
            else:
                crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="failed")
                
                # If fallback response is available, return it as structured error
                if 'fallback_response' in retry_result:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=200,  # Use 200 but indicate failure in response
                        content={
                            "status": "analysis_failed",
                            "fallback_provided": True,
                            "retry_result": retry_result
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to fix bug after {retry_result['total_attempts']} attempts. "
                               f"Last error: {retry_result.get('last_error', 'Unknown')}"
                    )
        else:
            # Single attempt (original behavior)
            result = await agent.analyze_error(
                error_message=request.error_message,
                code_snippet=request.code_snippet,
                file_path=request.file_path,
                additional_context=request.additional_context
            )
            
            # Update session usage in DB
            usage = result.get('usage', {})
            crud.update_session_usage(
                db=db, 
                session_id=session_id, 
                prompt_tokens=usage.get('prompt_tokens', 0), 
                completion_tokens=usage.get('completion_tokens', 0), 
                estimated_cost=usage.get('estimated_cost', 0.0)
            )
            
            # Update bug report status
            crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="analyzed")
            
            return BugAnalysisResponse(
                bug_id=bug_id,
                root_cause=result['root_cause'],
                fixed_code=result['fixed_code'],
                explanation=result['explanation'],
                confidence=result['confidence'],
                original_error=request.error_message,
                timestamp=result['timestamp'],
                usage={
                    **usage,
                    "session_id": session_id
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/fix-with-retry", response_model=RetryFixResponse)
async def fix_bug_with_retry(request: RetryFixRequest, db: Session = Depends(get_db)):
    """
    Analyze and fix a bug with automatic retry logic.
    
    This endpoint provides detailed information about all retry attempts:
    - Attempts up to max_attempts times (default: 3, max: 5)
    - Each attempt learns from previous failures
    - Returns all attempts with their verification results
    - Useful for debugging the AI's fix process
    
    Args:
        request: Fix request with retry parameters
        db: Database session
        
    Returns:
        Detailed results including all attempts and final outcome
    """
    try:
        # Create bug report in database
        bug_report = crud.create_bug_report(
            db=db,
            description=f"{request.error_message[:200]}..."
        )
        bug_id = f"BUG-{bug_report.id}"
        
        # Get API key
        api_key = request.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="OpenAI API key is required"
            )
        
        # Initialize agent and run retry logic
        agent = BugExorcistAgent(bug_id=bug_id, openai_api_key=api_key)
        result = await agent.analyze_and_fix_with_retry(
            error_message=request.error_message,
            code_snippet=request.code_snippet,
            file_path=request.file_path,
            additional_context=request.additional_context,
            max_attempts=request.max_attempts
        )
        
        # Update database status
        if result['success']:
            crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="fixed")
        else:
            crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="failed")
        
        return RetryFixResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retry fix failed: {str(e)}")


@router.post("/quick-fix", response_model=QuickFixResponse)
async def quick_fix_endpoint(request: QuickFixRequest):
    """
    Quick fix endpoint - returns only the fixed code without full analysis.
    
    Useful for simple, fast fixes where you don't need detailed explanations.
    Note: This endpoint does NOT use retry logic.
    
    Args:
        request: Quick fix request with error and code
        
    Returns:
        Only the fixed code
    """
    try:
        api_key = request.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="OpenAI API key is required"
            )
        
        fixed = await quick_fix(
            error=request.error,
            code=request.code,
            api_key=api_key
        )
        
        return QuickFixResponse(fixed_code=fixed)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quick fix failed: {str(e)}")


@router.get("/health")
async def agent_health():
    """
    Check if the agent system is operational.
    
    Returns:
        Health status and configuration info including retry and AI fallback capabilities
    """
    from core.gemini_agent import is_gemini_enabled, is_gemini_available
    
    api_key_set = bool(os.getenv("OPENAI_API_KEY"))
    gemini_key_set = bool(os.getenv("GEMINI_API_KEY"))
    gemini_enabled = is_gemini_enabled()
    gemini_available = is_gemini_available()
    
    return {
        "status": "operational",
        "agent": "Bug Exorcist",
        "primary_model": "gpt-4o",
        "fallback_model": "gemini-1.5-pro" if gemini_available else None,
        "api_key_configured": api_key_set,
        "gemini_key_configured": gemini_key_set,
        "gemini_fallback_enabled": gemini_enabled,
        "gemini_fallback_available": gemini_available,
        "langchain_available": True,
        "capabilities": [
            "error_analysis",
            "code_fixing",
            "root_cause_detection",
            "automated_verification",
            "automatic_retry_logic",
            "multi_ai_fallback"  # NEW
        ],
        "retry_config": {
            "enabled": True,
            "default_max_attempts": 3,
            "max_allowed_attempts": 5
        },
        "ai_fallback_chain": [
            "gpt-4o (primary)",
            "gemini-1.5-pro (fallback)" if gemini_available else "manual guidance (fallback)"
        ]
    }


@router.get("/bugs/{bug_id}/status")
async def get_bug_status(bug_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a bug report.
    
    Args:
        bug_id: ID of the bug report
        db: Database session
        
    Returns:
        Bug report details
    """
    bug_report = crud.get_bug_report(db, bug_id)
    
    if not bug_report:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    return {
        "id": bug_report.id,
        "description": bug_report.description,
        "status": bug_report.status,
        "created_at": bug_report.created_at.isoformat()
    }


@router.get("/bugs")
async def list_bugs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all bug reports.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of bug reports
    """
    bugs = crud.get_bug_reports(db, skip=skip, limit=limit)
    
    return {
        "bugs": [
            {
                "id": bug.id,
                "description": bug.description,
                "status": bug.status,
                "created_at": bug.created_at.isoformat()
            }
            for bug in bugs
        ],
        "count": len(bugs)
    }


@router.post("/bugs/{bug_id}/verify")
async def verify_bug_fix(bug_id: int, fixed_code: str, db: Session = Depends(get_db)):
    """
    Verify a bug fix by running it in a sandbox.
    
    Args:
        bug_id: ID of the bug report
        fixed_code: The fixed code to verify
        db: Database session
        
    Returns:
        Verification results
    """
    bug_report = crud.get_bug_report(db, bug_id)
    
    if not bug_report:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Initialize agent
    agent = BugExorcistAgent(bug_id=f"BUG-{bug_id}")
    
    # Verify the fix
    verification = await agent.verify_fix(fixed_code)
    
    # Update status if verified
    if verification['verified']:
        crud.update_bug_report_status(db=db, bug_report_id=bug_id, status="verified")
    else:
        crud.update_bug_report_status(db=db, bug_report_id=bug_id, status="verification_failed")
    
    return verification


@router.post("/test-connection")
async def test_openai_connection(api_key: Optional[str] = None):
    """
    Test the OpenAI API connection.
    
    Args:
        api_key: Optional API key to test (uses env if not provided)
        
    Returns:
        Connection test results
    """
    test_key = api_key or os.getenv("OPENAI_API_KEY")
    
    if not test_key:
        return {
            "success": False,
            "error": "No API key provided"
        }
    
    try:
        # Simple test with a minimal agent
        agent = BugExorcistAgent(bug_id="test", openai_api_key=test_key)
        
        # Try a simple analysis
        test_result = await agent.analyze_error(
            error_message="Test error",
            code_snippet="print('test')"
        )
        
        return {
            "success": True,
            "message": "OpenAI connection successful",
            "model": "gpt-4o",
            "test_confidence": test_result.get('confidence', 0.0),
            "retry_enabled": True
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }