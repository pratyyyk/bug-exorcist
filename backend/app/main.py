"""
backend/app/main.py - Main FastAPI Application

Enhanced with Bug Exorcist Agent integration and WebSocket streaming.
"""

import os
import json
from dotenv import load_dotenv
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
def health_check():
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
async def thought_stream_websocket(websocket: WebSocket, session_id: str):
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
            # Create bug report
            bug_report = crud.create_bug_report(
                db=db,
                description=f"{error_message[:200]}..."
            )
            bug_id = f"BUG-{bug_report.id}"
            
            # Get API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                await websocket.send_json({
                    "type": "error",
                    "timestamp": __import__('datetime').datetime.now().isoformat(),
                    "message": "OpenAI API key not configured",
                    "stage": "initialization"
                })
                await websocket.close()
                return
            
            # Initialize agent with streaming capability
            agent = BugExorcistAgent(bug_id=bug_id, openai_api_key=api_key)
            
            # Stream the thought process
            async for event in agent.stream_thought_process(
                error_message=error_message,
                code_snippet=code_snippet,
                file_path=file_path,
                additional_context=additional_context,
                use_retry=use_retry,
                max_attempts=max_attempts
            ):
                # Send each thought event to the client
                await websocket.send_json(event)
            
            # Update bug status in database based on final result
            # (This would be determined by the last event)
            
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": f"Agent error: {str(e)}",
                "stage": "error",
                "data": {"error": str(e)}
            })
        finally:
            db.close()
        
    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected from session {session_id}")
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "message": "Invalid JSON format in request",
            "stage": "initialization"
        })
    except Exception as e:
        print(f"[WebSocket] Error in session {session_id}: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "message": f"Server error: {str(e)}",
                "stage": "error"
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@app.get("/")
async def root():
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
async def startup_event():
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
async def shutdown_event():
    """Run on application shutdown"""
    print("🧟‍♂️ Bug Exorcist API shutting down...")