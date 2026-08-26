from apscheduler.schedulers.background import BackgroundScheduler
from src.tasks.process_data import scrape_and_insert
from src.config import get_logger
from datetime import datetime, timezone

scheduler = BackgroundScheduler()
logger = get_logger(__name__)

def start_scheduler():
    scheduler.add_job(
        scrape_and_insert.delay,
        trigger="cron",
        minute="*/5",
        args=('.net developer', 'chennai', 2),
        id="add_every_minute",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started at {datetime.now(timezone.utc)}")

def stop_scheduler():
    scheduler.shutdown()
    logger.info(f"Scheduler stopped at {datetime.now(timezone.utc)}")