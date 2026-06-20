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
from src.api.retrieval import router as retrieval_router
from src.api.insights import router as insights_router
from src.api.editorial import router as editorial_router
from src.api.pipeline import router as pipeline_router

app.include_router(incidents_router)
app.include_router(retrieval_router)
app.include_router(insights_router)
app.include_router(editorial_router)
app.include_router(pipeline_router)
