"""
backend/app/main.py - Main FastAPI Application

Enhanced with Bug Exorcist Agent integration and WebSocket streaming.
"""

import os
import json
import logging
import re
import datetime
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Path validation helper
def validate_paths(repo_path: Optional[str], file_path: Optional[str] = None, project_path: Optional[str] = None) -> bool:
    """
    Validates that repo_path, file_path, and project_path are safe and authorized.
    """
    try:
        allowed_root_env = os.getenv("ALLOWED_REPO_ROOT")
        root_dir = Path(allowed_root_env).resolve() if allowed_root_env else None

        if repo_path:
            repo_dir = Path(repo_path).resolve()
            if not repo_dir.is_dir():
                return False
            
            if root_dir and root_dir not in repo_dir.parents and root_dir != repo_dir:
                return False
                
            if file_path:
                target_file = (repo_dir / file_path).resolve()
                if repo_dir not in target_file.parents and repo_dir != target_file:
                    return False

        if project_path:
            proj_dir = Path(project_path).resolve()
            if not proj_dir.is_dir():
                return False
            
            if root_dir and root_dir not in proj_dir.parents and root_dir != proj_dir:
                return False
                
        return True
    except Exception:
        return False

# NEW: Structured JSON Logging Formatter
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("bug-exorcist-backend")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Valid supported languages
SUPPORTED_LANGUAGES = ["python", "javascript", "nodejs", "go", "rust", "bash", "go-test", "cargo-test", "npm-test"]

def sanitize_language(lang: str) -> str:
    """Sanitize and validate language input."""
    if not lang or not isinstance(lang, str):
        return "python"
    
    # Normalize: lowercase, strip, and remove any non-alphanumeric chars (except hyphens)
    clean_lang = re.sub(r'[^a-zA-Z0-9\-]', '', lang.lower().strip())
    
    # Check against supported list
    if clean_lang in SUPPORTED_LANGUAGES:
        return clean_lang
    
    # Specific mappings for common variations
    if clean_lang in ["js", "javascript"] or "javascript" in clean_lang: return "javascript"
    if clean_lang in ["node", "nodejs"] or "node" in clean_lang: return "nodejs"
    if clean_lang in ["golang", "go"] or "go" in clean_lang: return "go"
    if clean_lang in ["sh", "bash", "shell"] or "bash" in clean_lang: return "bash"
    if "npm" in clean_lang and "test" in clean_lang: return "npm-test"
    if "go" in clean_lang and "test" in clean_lang: return "go-test"
    if "cargo" in clean_lang and "test" in clean_lang: return "cargo-test"
    
    # Default to python if unknown or potentially dangerous
    return "python"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.api.logs import router as logs_router
from app.api.agent import router as agent_router
from app.database import engine, Base
from sqlalchemy import text

# Load environment variables from .env file
load_dotenv()

def run_migrations():
    """Lightweight startup migration routine to add missing columns to sessions table."""
    logger.info("Checking for database migrations...")
    try:
        with engine.connect() as conn:
            # Check existing columns in sessions table
            result = conn.execute(text("PRAGMA table_info(sessions)"))
            columns = [row[1] for row in result.fetchall()]
            
            # Add missing columns if they don't exist
            if "is_approved" not in columns:
                logger.info("Adding 'is_approved' column to sessions table")
                conn.execute(text("ALTER TABLE sessions ADD COLUMN is_approved INTEGER DEFAULT 0"))
            
            if "fixed_code" not in columns:
                logger.info("Adding 'fixed_code' column to sessions table")
                conn.execute(text("ALTER TABLE sessions ADD COLUMN fixed_code TEXT"))
            
            if "repo_path" not in columns:
                logger.info("Adding 'repo_path' column to sessions table")
                conn.execute(text("ALTER TABLE sessions ADD COLUMN repo_path TEXT"))
                
            if "file_path" not in columns:
                logger.info("Adding 'file_path' column to sessions table")
                conn.execute(text("ALTER TABLE sessions ADD COLUMN file_path TEXT"))
            
            conn.commit()
            logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error during database migration: {e}")

# Create database tables
Base.metadata.create_all(bind=engine)
# Run custom migrations for existing tables
run_migrations()

app = FastAPI(
    title="Bug Exorcist API",
    description="Autonomous AI-powered debugging system with GPT-4o integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Health check endpoint
@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "active",
        "service": "Bug Exorcist",
        "version": "1.0.0",
        "features": [
            "autonomous_debugging",
            "gpt4o_integration",
            "docker_sandboxing",
            "git_operations",
            "websocket_logging",
            "realtime_thought_stream"
        ]
    }

# Configure CORS (Essential for frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",  # Alternative port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(logs_router, tags=["logs"])
app.include_router(agent_router, tags=["agent"])


# NEW: Real-Time Thought Stream WebSocket Endpoint
@app.websocket("/ws/thought-stream/{session_id}")
async def thought_stream_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket endpoint for real-time AI thought streaming.
    
    This endpoint maintains a persistent connection and streams
    thought events as JSON objects in real-time as the agent processes.
    
    Expected message format from client:
    {
        "action": "analyze",
        "error_message": "...",
        "code_snippet": "...",
        "file_path": "...",
        "additional_context": "...",
        "use_retry": true,
        "max_attempts": 3
    }
    
    Streamed event format to client:
    {
        "type": "thought" | "status" | "result" | "error",
        "timestamp": "2024-01-26T10:30:00Z",
        "message": "...",
        "data": { ... },
        "stage": "initialization" | "analysis" | "fixing" | "verification" | "complete"
    }
    """
    # Validate session_id format and length
    if not session_id or len(session_id) > 100 or not re.match(r"^[a-zA-Z0-9\-_]+$", session_id):
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "message": "Invalid session ID format. Must be alphanumeric (plus - and _) and max 100 characters.",
            "stage": "initialization"
        })
        await websocket.close()
        return

    await websocket.accept()
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "status",
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "message": f"Connected to thought stream for session {session_id}",
            "stage": "initialization"
        })
        
        # Wait for client message with the bug analysis request
        request_data = await websocket.receive_json()
        
        # Validate request
        if request_data.get("action") != "analyze":
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": "Invalid action. Expected 'analyze'.",
                "stage": "initialization"
            })
            await websocket.close()
            return
        
        # Extract parameters
        error_message = request_data.get("error_message", "")
        code_snippet = request_data.get("code_snippet", "")
        file_path = request_data.get("file_path")
        repo_path = request_data.get("repo_path") # Optional: used for git operations
        project_path = request_data.get("project_path", repo_path or ".")
        
        # Security: Validate paths to prevent traversal
        if not validate_paths(repo_path, file_path, project_path):
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": "Invalid or unauthorized repository/file/project path.",
                "stage": "initialization"
            })
            await websocket.close()
            return

        additional_context = request_data.get("additional_context")
        use_retry = request_data.get("use_retry", True)
        max_attempts = request_data.get("max_attempts", 3)
        language = sanitize_language(request_data.get("language", "python"))
        require_approval = os.getenv("REQUIRE_APPROVAL", "false").lower() == "true"
        
        # Validate required fields
        if not error_message or not code_snippet:
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": "Missing required fields: error_message and code_snippet",
                "stage": "initialization"
            })
            await websocket.close()
            return
        
        # Import agent here to avoid circular imports
        from core.agent import BugExorcistAgent
        from app import crud
        from app.database import SessionLocal
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Check if session already exists to prevent hijacking/overwriting
            existing_session = crud.get_session(db=db, session_id=session_id)
            if existing_session:
                await websocket.send_json({
                    "type": "error",
                    "timestamp": __import__('datetime').datetime.now().isoformat(),
                    "message": f"Session {session_id} already exists. Please use a unique session ID.",
                    "stage": "initialization"
                })
                await websocket.close()
                return

            # Create bug report
            bug_report = crud.create_bug_report(
                db=db,
                description=f"{error_message[:200]}..."
            )
            bug_id = f"BUG-{bug_report.id}"
            
            # Create session for tracking
            crud.create_session(db=db, session_id=session_id, bug_report_id=bug_report.id)
            
            # Initialize usage tracking
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_cost = 0.0
            
            # Initialize agent with streaming capability
            agent = BugExorcistAgent(bug_id=bug_id, project_path=project_path)
            
            # Start thought stream
            last_result = None
            async for event in agent.stream_thought_process(
                error_message=error_message,
                code_snippet=code_snippet,
                file_path=file_path,
                additional_context=additional_context,
                use_retry=use_retry,
                max_attempts=max_attempts,
                language=language
            ):
                if event.get("type") == "result":
                    last_result = event.get("data")
                # If this is a thought event with usage, accumulate it
                if event.get("type") == "thought" and "usage" in event.get("data", {}):
                    usage = event["data"]["usage"]
                    total_prompt_tokens += usage.get("prompt_tokens", 0)
                    total_completion_tokens += usage.get("completion_tokens", 0)
                    total_cost += usage.get("estimated_cost", 0.0)
                    
                    # Update session in DB
                    crud.update_session_usage(
                        db=db,
                        session_id=session_id,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        estimated_cost=usage.get("estimated_cost", 0.0)
                    )
                
                # If this is the final result, add total usage to it
                if event.get("type") == "result":
                    event["data"]["usage"] = {
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                        "estimated_cost": f"{total_cost:.6f}",
                        "session_id": session_id
                    }
                
                # Send each thought event to the client
                await websocket.send_json(event)
                
                # Check if we need approval before concluding
                if require_approval and event.get("type") == "result" and event.get("data", {}).get("success"):
                    final_fix_code = event.get("data", {}).get("fixed_code")
                    
                    if final_fix_code:
                        # Generate diff for the approval request
                        patch = ""
                        try:
                            import difflib
                            original_content = ""
                            if repo_path and file_path:
                                # Construct full path safely
                                full_path = (Path(repo_path) / file_path).resolve()
                                if full_path.exists() and validate_paths(repo_path, file_path):
                                    with open(full_path, 'r', encoding='utf-8') as f:
                                        original_content = f.read()
                            
                            if not original_content and code_snippet:
                                original_content = code_snippet
                                
                            diff = difflib.unified_diff(
                                original_content.splitlines(keepends=True),
                                final_fix_code.splitlines(keepends=True),
                                fromfile=f'a/{file_path or "original"}',
                                tofile=f'b/{file_path or "fixed"}'
                            )
                            patch = "".join(diff)
                        except Exception as e:
                            logger.error(f"Failed to generate diff: {e}")
                            patch = f"Could not generate diff. Previewing fixed code:\n\n{final_fix_code}"

                        crud.update_session_approval(
                            db=db, 
                            session_id=session_id, 
                            is_approved=0, 
                            fixed_code=final_fix_code,
                            repo_path=repo_path,
                            file_path=file_path
                        )

                    await websocket.send_json({
                        "type": "APPROVAL_REQUEST",
                        "timestamp": __import__('datetime').datetime.now().isoformat(),
                        "message": "✋ Fix generated. Awaiting user approval before applying.",
                        "stage": "awaiting_approval",
                        "data": {
                            "require_approval": True,
                            "fixed_code": final_fix_code,
                            "patch": patch,
                            "file_path": file_path
                        }
                    })
                    
                    # Wait for approval/rejection with timeout and disconnect handling
                    try:
                        approval_data = await asyncio.wait_for(websocket.receive_json(), timeout=60)
                        if approval_data.get("action") == "approve":
                            await websocket.send_json({
                                "type": "status",
                                "timestamp": __import__('datetime').datetime.now().isoformat(),
                                "message": "✅ Fix approved. Applying to repository...",
                                "stage": "applying_fix"
                            })
                            
                            # Apply Git fix if repo_path is provided and valid
                            if repo_path and file_path and final_fix_code and validate_paths(repo_path, file_path):
                                from app.git_ops import apply_fix_to_repo
                                git_res = apply_fix_to_repo(
                                    repo_path=repo_path,
                                    bug_id=bug_id,
                                    file_path=file_path,
                                    fixed_code=final_fix_code
                                )
                                await websocket.send_json({
                                    "type": "thought",
                                    "timestamp": __import__('datetime').datetime.now().isoformat(),
                                    "message": git_res,
                                    "stage": "applying_fix"
                                })
                            
                            crud.update_session_approval(db=db, session_id=session_id, is_approved=1)
                        else:
                            await websocket.send_json({
                                "type": "status",
                                "timestamp": __import__('datetime').datetime.now().isoformat(),
                                "message": "❌ Fix rejected by user.",
                                "stage": "rejected"
                            })
                            crud.update_session_approval(db=db, session_id=session_id, is_approved=-1)
                    except asyncio.TimeoutError:
                        logger.warning(f"Approval request timed out for session {session_id}")
                        crud.update_session_approval(db=db, session_id=session_id, is_approved=-1)
                        await websocket.send_json({
                            "type": "error",
                            "timestamp": __import__('datetime').datetime.now().isoformat(),
                            "message": "Approval request timed out (60s limit). Fix rejected.",
                            "stage": "rejected"
                        })
                        break
                    except WebSocketDisconnect:
                        logger.info(f"Client disconnected during approval for session {session_id}")
                        crud.update_session_approval(db=db, session_id=session_id, is_approved=-1)
                        return # Exit the function immediately
                    except Exception as e:
                        logger.error(f"Error during approval process: {e}")
                        crud.update_session_approval(db=db, session_id=session_id, is_approved=-1)
                        break
            
            # Update bug status in database based on final result
            # (This would be determined by the last event)
            
        except Exception as e:
            logger.exception(f"Agent error in session {session_id}")
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": "An error occurred during agent analysis. Please try again later.",
                "stage": "error"
            })
        finally:
            db.close()
        
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected from session {session_id}")
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "message": "Invalid JSON format in request",
            "stage": "initialization"
        })
    except Exception as e:
        logger.exception(f"WebSocket error in session {session_id}")
        try:
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": "Internal server error. Please try again later.",
                "stage": "error"
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "message": "🧟‍♂️ Bug Exorcist API is running",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "analyze_bug": "POST /api/agent/analyze",
            "quick_fix": "POST /api/agent/quick-fix",
            "agent_health": "GET /api/agent/health",
            "websocket_logs": "WS /ws/logs/{bug_id}",
            "thought_stream": "WS /ws/thought-stream/{session_id}"
        }
    }

@app.on_event("startup")
async def startup_event() -> None:
    """Run on application startup"""
    print("🧟‍♂️ Bug Exorcist API Starting...")
    print("=" * 60)
    print("📡 WebSocket logging: /ws/logs/{bug_id}")
    print("🧠 Thought stream: /ws/thought-stream/{session_id}")
    print("🤖 Agent analysis: POST /api/agent/analyze")
    print("⚡ Quick fix: POST /api/agent/quick-fix")
    print("📚 Documentation: http://localhost:8000/docs")
    print("=" * 60)

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Run on application shutdown"""
    print("🧟‍♂️ Bug Exorcist API shutting down...")