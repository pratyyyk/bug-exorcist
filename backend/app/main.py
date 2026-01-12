from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.logs import router as logs_router

app = FastAPI(title="Bug Exorcist API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(logs_router)

@app.get("/")
async def root():
    return {"message": "Bug Exorcist API is running"}
