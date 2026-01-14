from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.logs import router as logs_router

# Import database components - these will be needed for DB support
# from .database import engine 
# from . import models

# Initialize database tables
# models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bug Exorcist API")

# Configure CORS (Essential for frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (Including the log streaming WebSocket)
app.include_router(logs_router)

@app.get("/")
async def root():
    return {"message": "Bug Exorcist API is running"}
