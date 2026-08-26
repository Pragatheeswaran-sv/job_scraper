from contextlib import asynccontextmanager
from fastapi import FastAPI

from scheduler import start_scheduler, stop_scheduler
from src.config import get_logger
from src.jwt_auth.api import router as auth_router
from src.jobs.api import router as job_router
from src.background_task.api import router as scrap_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    logger.info("Job Scraper starting up")
    yield
    stop_scheduler()
    logger.info("Job Scraper shutting down")


app = FastAPI(
    title="Job Scraper",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(job_router)
app.include_router(scrap_router)


@app.get("/health_check")
def health_check():
    return {"message": "Job Scraper is running"}


