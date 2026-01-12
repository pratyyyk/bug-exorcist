from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

router = APIRouter()

@router.websocket("/ws/logs/{bug_id}")
async def websocket_endpoint(websocket: WebSocket, bug_id: str):
    await websocket.accept()
    try:
        # Dummy data streaming
        for i in range(1, 11):
            log_message = f"[DEBUG] Bug {bug_id}: Processing step {i}..."
            await websocket.send_text(log_message)
            await asyncio.sleep(1)
        
        await websocket.send_text(f"[INFO] Log streaming completed for bug {bug_id}")
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
        except:
            pass
