import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.postgres import init_db, close_db
from app.api.routes import router

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    logger.info("Starting RT API...")
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down RT API...")
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title="Rotten Tomatoes API",
    description="A personal API for fetching Rotten Tomatoes movie data",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Cine Match integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["movies"])


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Rotten Tomatoes API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
