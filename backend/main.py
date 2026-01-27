"""
TuffWraps Marketing API

FastAPI backend for the marketing attribution dashboard.
Exposes all data and action endpoints for the Next.js frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from routers import metrics, actions, changelog, ai_chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("Starting TuffWraps Marketing API...")
    yield
    print("Shutting down...")


app = FastAPI(
    title="TuffWraps Marketing API",
    description="Backend API for marketing attribution dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(actions.router, prefix="/api/actions", tags=["Actions"])
app.include_router(changelog.router, prefix="/api/changelog", tags=["Changelog"])
app.include_router(ai_chat.router, prefix="/api/ai", tags=["AI Chat"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "TuffWraps Marketing API"}


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "endpoints": [
            "/api/metrics",
            "/api/actions",
            "/api/changelog",
            "/api/ai",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
