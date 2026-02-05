"""
backend/app/api/agent.py - FastAPI endpoints for Bug Exorcist Agent

This module provides REST API endpoints to interact with the autonomous debugging agent.
Enhanced with automatic retry logic for failed fixes.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Generator
from sqlalchemy.orm import Session
import os
import logging

logger = logging.getLogger(__name__)

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
    language: str = Field("python", description="The programming language of the code")
    additional_context: Optional[str] = Field(None, description="Additional context about the bug")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key (optional, uses env if not provided)")
    use_retry: bool = Field(True, description="Enable automatic retry logic (default: True)")
    max_attempts: int = Field(3, description="Maximum retry attempts (default: 3, max: 5)", ge=1, le=5)

    @validator("language")
    def validate_language(cls, v):
        from app.main import sanitize_language
        return sanitize_language(v)

    class Config:
        json_schema_extra = {
            "example": {
                "error_message": "ZeroDivisionError: division by zero\n  File 'calc.py', line 10",
                "code_snippet": "def divide(a, b):\n    return a / b",
                "file_path": "calc.py",
                "language": "python",
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
    language: str = "python"
    timestamp: str
    attempt_number: Optional[int] = 1
    usage: Optional[Dict[str, Any]] = None


class RetryFixRequest(BaseModel):
    """Request model for fix with retry logic"""
    error_message: str
    code_snippet: str
    file_path: Optional[str] = None
    language: str = Field("python", description="The programming language of the code")
    additional_context: Optional[str] = None
    openai_api_key: Optional[str] = None
    max_attempts: int = Field(3, ge=1, le=5)

    @validator("language")
    def validate_language(cls, v):
        from app.main import sanitize_language
        return sanitize_language(v)


class RetryFixResponse(BaseModel):
    """Response model for retry fix"""
    success: bool
    final_fix: Optional[Dict[str, Any]]
    all_attempts: List[Dict[str, Any]]
    total_attempts: int
    message: str
    language: str = "python"
    last_error: Optional[str] = None


class VerifyFixRequest(BaseModel):
    """Request model for bug fix verification"""
    fixed_code: str = Field(..., description="The fixed code to verify")
    language: str = Field("python", description="The programming language of the code")

    @validator("language")
    def validate_language(cls, v):
        from app.main import sanitize_language
        return sanitize_language(v)


class QuickFixRequest(BaseModel):
    """Request model for quick fix"""
    error: str
    code: str
    language: str = Field("python", description="The programming language of the code")
    openai_api_key: Optional[str] = None

    @validator("language")
    def validate_language(cls, v):
        from app.main import sanitize_language
        return sanitize_language(v)


class QuickFixResponse(BaseModel):
    """Response model for quick fix"""
    fixed_code: str


class BugStatusResponse(BaseModel):
    """Response model for bug status"""
    id: int
    description: str
    status: str
    created_at: str


class BugListResponse(BaseModel):
    """Response model for bug list"""
    bugs: List[BugStatusResponse]
    count: int


class VerificationResponse(BaseModel):
    """Response model for bug fix verification"""
    verified: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class ConnectionTestResponse(BaseModel):
    """Response model for OpenAI connection test"""
    success: bool
    message: Optional[str] = None
    model: Optional[str] = None
    test_confidence: Optional[float] = None
    retry_enabled: Optional[bool] = None
    error: Optional[str] = None


class AgentHealthResponse(BaseModel):
    """Response model for agent health check"""
    status: str
    agent: str
    primary_model: str
    fallback_model: Optional[str] = None
    api_key_configured: bool
    gemini_key_configured: bool = False
    gemini_fallback_enabled: bool = False
    gemini_fallback_available: bool = False
    ollama_available: bool = False
    langchain_available: bool
    capabilities: List[str]
    retry_config: Dict[str, Any]
    ai_fallback_chain: List[str]


# Dependency for database session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/analyze", response_model=BugAnalysisResponse)
async def analyze_bug(request: BugAnalysisRequest, db: Session = Depends(get_db)) -> BugAnalysisResponse:
    """
    Analyze a bug and generate a fix using the configured AI agent.
    """
    try:
        # Create bug report in database
        bug_report = crud.create_bug_report(
            db=db,
            description=f"{request.error_message[:200]}..."
        )
        bug_id = f"BUG-{bug_report.id}"
        
        # Create a session for tracking usage
        import uuid
        session_id = str(uuid.uuid4())
        crud.create_session(db=db, session_id=session_id, bug_report_id=bug_report.id)
        
        # Initialize agent
        agent = BugExorcistAgent(bug_id=bug_id, openai_api_key=request.openai_api_key)
        
        if request.use_retry:
            # Use retry logic
            retry_result = await agent.analyze_and_fix_with_retry(
                error_message=request.error_message,
                code_snippet=request.code_snippet,
                file_path=request.file_path,
                additional_context=request.additional_context,
                max_attempts=request.max_attempts,
                language=request.language
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
                    language=request.language,
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
                    logger.error(f"Analysis failed for {bug_id} after {retry_result['total_attempts']} attempts. Last error: {retry_result.get('last_error', 'Unknown')}")
                    raise HTTPException(
                        status_code=500,
                        detail="Analysis failed: Maximum retry attempts reached without a valid fix."
                    )
        else:
            # Single attempt (original behavior)
            result = await agent.analyze_error(
                error_message=request.error_message,
                code_snippet=request.code_snippet,
                file_path=request.file_path,
                additional_context=request.additional_context,
                language=request.language
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
                language=request.language,
                timestamp=result['timestamp'],
                usage={
                    **usage,
                    "session_id": session_id
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during analysis for {bug_id if 'bug_id' in locals() else 'unknown session'}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during bug analysis. Please try again.")


@router.post("/fix-with-retry", response_model=RetryFixResponse)
async def fix_bug_with_retry(request: RetryFixRequest, db: Session = Depends(get_db)) -> RetryFixResponse:
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
        
        # Initialize agent and run retry logic
        agent = BugExorcistAgent(bug_id=bug_id, openai_api_key=request.openai_api_key)
        result = await agent.analyze_and_fix_with_retry(
            error_message=request.error_message,
            code_snippet=request.code_snippet,
            file_path=request.file_path,
            additional_context=request.additional_context,
            max_attempts=request.max_attempts,
            language=request.language
        )
        
        # Update database status
        if result['success']:
            crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="fixed")
        else:
            crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="failed")
        
        return RetryFixResponse(language=request.language, **result)
        
    except Exception as e:
        logger.exception(f"Retry fix failed for {bug_id if 'bug_id' in locals() else 'unknown'}")
        raise HTTPException(status_code=500, detail="Retry fix process failed. Please check server logs.")


@router.post("/quick-fix", response_model=QuickFixResponse)
async def quick_fix_endpoint(request: QuickFixRequest) -> QuickFixResponse:
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
        fixed = await quick_fix(
            error=request.error,
            code=request.code,
            language=request.language,
            api_key=request.openai_api_key
        )
        
        return QuickFixResponse(fixed_code=fixed)
        
    except Exception as e:
        logger.exception("Quick fix failed")
        raise HTTPException(status_code=500, detail="Quick fix failed. Please check server logs.")


@router.get("/health", response_model=AgentHealthResponse)
async def agent_health() -> AgentHealthResponse:
    """
    Check if the agent system is operational.
    
    Returns:
        Health status and configuration info including retry and AI fallback capabilities
    """
    from core.gemini_agent import is_gemini_enabled, is_gemini_available
    from core.ollama_provider import is_ollama_available
    
    api_key_set = bool(os.getenv("OPENAI_API_KEY"))
    gemini_key_set = bool(os.getenv("GEMINI_API_KEY"))
    gemini_enabled = is_gemini_enabled()
    gemini_available = is_gemini_available()
    ollama_available = is_ollama_available()
    
    primary_agent = os.getenv("PRIMARY_AGENT", "gpt-4o")
    secondary_agent = os.getenv("SECONDARY_AGENT", "gemini-1.5-pro")
    
    return AgentHealthResponse(
        status="operational",
        agent="Bug Exorcist",
        primary_model=primary_agent,
        fallback_model=secondary_agent,
        api_key_configured=api_key_set,
        gemini_key_configured=gemini_key_set,
        gemini_fallback_enabled=gemini_enabled,
        gemini_fallback_available=gemini_available,
        ollama_available=ollama_available,
        langchain_available=True,
        capabilities=[
            "error_analysis",
            "code_fixing",
            "root_cause_detection",
            "automated_verification",
            "automatic_retry_logic",
            "multi_ai_fallback",
            *(["local_llm_support"] if ollama_available else [])
        ],
        retry_config={
            "enabled": True,
            "default_max_attempts": 3,
            "max_allowed_attempts": 5
        },
        ai_fallback_chain=[
            f"{primary_agent} (primary)",
            f"{secondary_agent} (secondary)" if secondary_agent else "manual guidance (fallback)"
        ]
    )


@router.get("/bugs/{bug_id}/status", response_model=BugStatusResponse)
async def get_bug_status(bug_id: str, db: Session = Depends(get_db)) -> BugStatusResponse:
    """
    Get the status of a bug report.
    
    Args:
        bug_id: ID of the bug report (format: "BUG-{numeric_id}")
        db: Database session
        
    Returns:
        Bug report details
    """
    # Parse numeric ID from "BUG-{id}" format
    if bug_id.startswith("BUG-"):
        numeric_id = int(bug_id.replace("BUG-", ""))
    else:
        # If no prefix, try to parse as int directly
        numeric_id = int(bug_id)
    
    bug_report = crud.get_bug_report(db, numeric_id)
    
    if not bug_report:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    return BugStatusResponse(
        id=bug_report.id,
        description=bug_report.description,
        status=bug_report.status,
        created_at=bug_report.created_at.isoformat()
    )


@router.get("/bugs", response_model=BugListResponse)
async def list_bugs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> BugListResponse:
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
    
    bug_responses = [
        BugStatusResponse(
            id=bug.id,
            description=bug.description,
            status=bug.status,
            created_at=bug.created_at.isoformat()
        )
        for bug in bugs
    ]
    
    return BugListResponse(
        bugs=bug_responses,
        count=len(bug_responses)
    )

@router.post("/bugs/{bug_id}/verify", response_model=VerificationResponse)
async def verify_bug_fix(bug_id: str, request: VerifyFixRequest, db: Session = Depends(get_db)) -> VerificationResponse:
    """
    Verify a bug fix by running it in a sandbox.
    
    Args:
        bug_id: ID of the bug report (format: "BUG-{numeric_id}")
        request: Request containing the fixed code to verify
        db: Database session
        
    Returns:
        Verification results
    """
    # Parse numeric ID from "BUG-{id}" format with proper error handling
    try:
        if bug_id.startswith("BUG-"):
            numeric_id = int(bug_id.replace("BUG-", ""))
        else:
            # If no prefix, try to parse as int directly
            numeric_id = int(bug_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bug_id format: '{bug_id}'. Expected format: 'BUG-{{numeric_id}}' or plain numeric ID"
        )
    
    bug_report = crud.get_bug_report(db, numeric_id)
    
    if not bug_report:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Initialize agent
    agent = BugExorcistAgent(bug_id=f"BUG-{numeric_id}")
    
    # Verify the fix
    verification = await agent.verify_fix(request.fixed_code, language=request.language)
    
    # Update status if verified
    if verification['verified']:
        crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="verified")
    else:
        crud.update_bug_report_status(db=db, bug_report_id=bug_report.id, status="verification_failed")
    
    return VerificationResponse(**verification)


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_agent_connection(api_key: Optional[str] = None) -> ConnectionTestResponse:
    """
    Test the connection to the configured primary AI agent.
    
    Args:
        api_key: Optional API key to test (uses env if not provided)
        
    Returns:
        Connection test results
    """
    try:
        # Simple test with a minimal agent
        agent = BugExorcistAgent(bug_id="test", openai_api_key=api_key)
        
        # Validate that the primary provider is actually configured
        # This prevents false-positives where the agent might fallback to a secondary provider
        if agent.primary_provider is None:
            primary_agent = os.getenv("PRIMARY_AGENT", "gpt-4o")
            return ConnectionTestResponse(
                success=False,
                message=f"Primary provider '{primary_agent}' is not configured or missing API key.",
                error="Configuration Error"
            )
            
        # Try a simple analysis
        test_result = await agent.analyze_error(
            error_message="Test error",
            code_snippet="print('test')"
        )
        
        # Report the actual model used for the test
        actual_model = test_result.get('ai_agent', 'unknown')
        
        return ConnectionTestResponse(
            success=True,
            message=f"Connection to {actual_model} successful",
            model=actual_model,
            test_confidence=test_result.get('confidence', 0.0),
            retry_enabled=True
        )
        
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            error=str(e)
        )