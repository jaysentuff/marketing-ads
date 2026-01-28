"""
TuffWraps Marketing API

FastAPI backend for the marketing attribution dashboard.
Exposes all data and action endpoints for the Next.js frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys
import os
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from routers import metrics, actions, changelog, ai_chat, ai_synthesis


def get_allowed_origins():
    """Get CORS allowed origins from environment or defaults."""
    # Check for custom origins via environment variable
    custom_origins = os.environ.get("CORS_ORIGINS", "")

    # Default origins for development
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Add custom origins if provided (comma-separated)
    if custom_origins:
        origins.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

    # In production, allow Railway domains
    railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if railway_url:
        origins.append(f"https://{railway_url}")

    # Also check for frontend URL
    frontend_url = os.environ.get("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)

    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("Starting TuffWraps Marketing API...")
    print(f"CORS allowed origins: {get_allowed_origins()}")
    yield
    print("Shutting down...")


app = FastAPI(
    title="TuffWraps Marketing API",
    description="Backend API for marketing attribution dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend - configured for both dev and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(actions.router, prefix="/api/actions", tags=["Actions"])
app.include_router(changelog.router, prefix="/api/changelog", tags=["Changelog"])
app.include_router(ai_chat.router, prefix="/api/ai", tags=["AI Chat"])
app.include_router(ai_synthesis.router, prefix="/api/synthesis", tags=["AI Synthesis"])


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
            "/api/synthesis",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
