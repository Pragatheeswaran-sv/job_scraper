from fastapi import APIRouter, HTTPException, status
from src.tasks.process_data import scrape_and_insert
from src.config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/scrape",
    tags=["scrape"],
)

@router.post("/scrap_jobs")
def scrape_jobs(search_keyword: str, search_location: str, max_jobs: int = None):
    try:
        result = scrape_and_insert.delay(search_keyword, search_location, max_jobs)
        return {
            "status_code": 202,
            "message": "Scrape task submitted",
            "task_id": result.id,
        }
    except Exception as e:
        logger.error("Error submitting scrape task: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit scrape task",
        )