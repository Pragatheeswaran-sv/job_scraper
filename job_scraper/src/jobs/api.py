from fastapi import APIRouter, Query
from src.config import get_logger
from src.jobs.service import export_scraped_jobs, get_posted_jobs
from src.utils.job_validator import validate_job_params
from fastapi import APIRouter, HTTPException, status

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["jobs"],
    responses={
        200: {"description": "ok"},
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)

@router.get('/list_jobs')
def list_jobs(page: int = 1, per_page: int = 10, filter_column: str = None, filter_value: str = None, sort_column: str = None, sort_by: str = None):
    errors = validate_job_params(page, per_page, filter_column, filter_value, sort_column, sort_by)
    if errors:
        return {
            "status_code": 400,
            "message": "Validation failed",
            "errors": errors
        }
    try:
        return get_posted_jobs(page, per_page, filter_column, filter_value, sort_column, sort_by)
    except Exception as e:
        logger.error('ERROR while listing jobs: %s', e)
        return {
            "status_code": 500,
            "message": "Error while listing jobs"
        }


@router.post("/export")
def export_jobs():
    try:
        result = export_scraped_jobs()
        return {
            "status_code": 200,
            "message": "Scrape task submitted",
            "data":result
        }
    except Exception as e:
        logger.error("Error submitting scrape task: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit scrape task",
        )