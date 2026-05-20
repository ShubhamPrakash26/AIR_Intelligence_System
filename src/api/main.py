from fastapi import FastAPI
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="AIR Clinical Incident Intelligence Engine API")


@app.get("/healthz")
async def healthz():
    """Simple health check endpoint."""
    logger.info("Health check requested")
    return {"status": "ok"}


# Include incident routes
from src.api.incidents import router as incidents_router

app.include_router(incidents_router)
