"""
backend/app/main.py - Main FastAPI Application

Enhanced with Bug Exorcist Agent integration and WebSocket streaming.
"""

import os
import json
import logging
import re
import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

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

# Load environment variables from .env file
load_dotenv()

# Create database tables
Base.metadata.create_all(bind=engine)

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
        additional_context = request_data.get("additional_context")
        use_retry = request_data.get("use_retry", True)
        max_attempts = request_data.get("max_attempts", 3)
        language = sanitize_language(request_data.get("language", "python"))
        
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
            agent = BugExorcistAgent(bug_id=bug_id)
            
            # Start thought stream
            async for event in agent.stream_thought_process(
                error_message=error_message,
                code_snippet=code_snippet,
                file_path=file_path,
                additional_context=additional_context,
                use_retry=use_retry,
                max_attempts=max_attempts,
                language=language
            ):
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