from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.agent import BugExorcistAgent
import asyncio

router = APIRouter()

@router.websocket("/ws/logs/{bug_id}")
async def websocket_endpoint(websocket: WebSocket, bug_id: str) -> None:
    await websocket.accept()
    agent = BugExorcistAgent(bug_id)
    try:
        async for log_message in agent.stream_logs():
            await websocket.send_text(log_message)
    except WebSocketDisconnect:
        # Connection closed by client
        pass
    except Exception as e:
        # Handle other potential errors
        print(f"WebSocket error for bug {bug_id}: {e}")
    finally:
        # Ensure the connection is closed
        try:
            await websocket.close()
        except Exception:
            pass
