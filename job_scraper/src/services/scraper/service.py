from sqlalchemy.orm import Session
from src.scraper.models import ScrapeRun
from fastapi import status

from src.config import get_logger

logger = get_logger(__name__)

def create_scrape_run(db: Session, scrape_status: str, records_scraped: int = 0, ended_at: str | None = None, exception: str | None = None) -> ScrapeRun:
    print(scrape_status, records_scraped, ended_at, exception)
    try:
        run = ScrapeRun(status=scrape_status, records_scraped=records_scraped, ended_at=ended_at, exception=exception)
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info("ScrapeRun inserted: %s", run.id)
        return {
            "status_code": status.HTTP_200_OK,
            "meassage": "scrape run added successfully",
            "data": {
                "run_id": run.id,
                "start_at": run.started_at,
                "status": run.status
            }
        }
    except Exception as e:
        db.rollback()
        run = ScrapeRun(status="failed", records_scraped=0, exception=str(e))
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info("ScrapeRun inserted with exception: %s", run.id)
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "meassage": "scrape run failed",
            "data": {
                "run_id": run.id,
                "start_at": run.started_at,
                "status": run.status
            }
        }