from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config import get_logger
from src.jwt_auth.api import router as auth_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Job Scraper starting up")
    yield
    logger.info("Job Scraper shutting down")


app = FastAPI(
    title="Job Scraper",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)


@app.get("/health_check")
def health_check():
    return {"message": "Job Scraper is running"}
