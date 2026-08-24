from datetime import datetime, timezone

from sqlalchemy.orm import Session
from src.background_task.models import ScrapeRun
from fastapi import status

from src.config import get_logger

logger = get_logger(__name__)

def create_scrape_run(db: Session, scrape_status: str, records_scraped: int = 0, ended_at: str | None = None, exception: str | None = None) -> ScrapeRun:
    try:
        run = ScrapeRun(status=scrape_status, records_scraped=records_scraped, ended_at=ended_at, exception=exception)
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info("ScrapeRun inserted: %s", run.id)
        return run.id
        
    except Exception as e:
        db.rollback()
        run = ScrapeRun(status="failed", records_scraped=0, exception=str(e))
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info("ScrapeRun inserted with exception: %s", run.id)
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "scrape run failed",
            "data": {
                "run_id": run.id,
                "start_at": run.started_at,
                "status": run.status
            }
        }

def update_scrape_run(db, run_id, scrape_status, records_scraped=0, exception=None):
    run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
    if not run:
        return None
    run.status = scrape_status
    run.records_scraped = records_scraped
    run.exception = exception
    run.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run