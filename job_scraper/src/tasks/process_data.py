import os

from src.celery_app import celery_app
from src.database import SessionLocal
from src.background_task.service import create_scrape_run, update_scrape_run
from src.company.service import create_company
from src.contact.service import create_contact
from src.jobs.service import create_skills
from src.jobs.models import Job
from src.scraper.linkedin import scrape_linkedin_jobs
from src.config import get_logger
import shutil

logger = get_logger(__name__)

@celery_app.task(name="tasks.scrape_and_insert")
def scrape_and_insert(search_keyword=None, search_location=None, max_jobs=10):
    db = SessionLocal()
    run_id = None
    try:
        run_id = create_scrape_run(db, scrape_status="pending")
        logger.info("ScrapeRun created: %s", run_id)

        scrape_result = scrape_linkedin_jobs(
            run_id,
            search_keyword=search_keyword,
            search_location=search_location,
            max_jobs=max_jobs,
        )

        if scrape_result["status_code"] != 200:
            update_scrape_run(db, run_id, "failed", exception=scrape_result.get("message"))
            return {"run_id": run_id, "status": "failed", "message": scrape_result.get("message")}

        jobs_data = scrape_result["data"]["jobs"]
        records_inserted = 0

        for job_json in jobs_data:
            company_result = create_company(
                db, 
                name=job_json.get("company", ""),
                run_id=run_id,
                location=job_json.get("company_location"),
                description=job_json.get("company_information")
            )
            company_id = company_result if isinstance(company_result, str) else None

            posted_by = job_json.get("posted_by", {})
            name_parts = posted_by.get("name", "").split(" ", 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            posted_by_contact_id = None
            if first_name:
                contact_result = create_contact(
                    db, 
                    first_name=first_name, 
                    last_name=last_name,
                    contact_url=posted_by.get("linkedin_url"),
                    company_id=company_id, 
                    run_id=run_id
                )
                posted_by_contact_id = contact_result if isinstance(contact_result, str) else None

            for rec in job_json.get("recommended_contacts", []):
                rec_parts = rec.get("name", "").split(" ", 1)
                if rec_parts[0]:
                    create_contact(
                        db,
                        first_name=rec_parts[0],
                        last_name=rec_parts[1] if len(rec_parts) > 1 else "",
                        contact_url=rec.get("linkedin_url"),
                        company_id=company_id, run_id=run_id
                    )

            salary = job_json.get("salary", {})
            experience = job_json.get("experience_required", {})

            job = Job(
                title=job_json.get("job_title", ""),
                location=job_json.get("job_location"),
                description=job_json.get("job_description"),
                min_experience=experience.get("min_exp"),
                max_experience=experience.get("max_exp"),
                education_required=job_json.get("education_required"),
                employment_type=job_json.get("employment_type"),
                min_salary=salary.get("min_sal"),
                max_salary=salary.get("max_sal"),
                currency_type=salary.get("currency"),
                salary_payment_period=salary.get("payment_period"),
                work_type=job_json.get("work_type"),
                source="LinkedIn",
                job_url=job_json.get("linkedin_job_url", ""),
                company_id=company_id,
                posted_by=posted_by_contact_id,
                run_id=run_id,
                is_active=True,
            )
            db.add(job)
            db.flush()

            create_skills(
                db, job.id,
                required_skills=job_json.get("required_skills", []),
                preferred_skills=job_json.get("preferred_skills", [])
            )

            raw_file_path = job_json.get("_raw_file_path")
            if raw_file_path and os.path.exists(raw_file_path):

                dir_name = os.path.dirname(raw_file_path)
                old_timestamp = os.path.basename(raw_file_path).split("_", 1)[1].replace(".txt", "")
                new_filename = f"{job.id}_{old_timestamp}.txt"
                new_path = os.path.join(dir_name, new_filename)
                os.rename(raw_file_path, new_path)

            records_inserted += 1

        db.commit()
        update_scrape_run(db, run_id, "success", records_scraped=records_inserted)
        shutil.rmtree(f"logs/{run_id}", ignore_errors=True)

        logger.info("Scrape completed: %s records", records_inserted)
        return {"run_id": run_id, "status": "success", "records": records_inserted}

    except Exception as e:
        db.rollback()
        logger.error("Scrape task failed: %s", e)
        if run_id:
            try:
                update_scrape_run(db, run_id, "failed", records_scraped=records_inserted, exception=str(e))
            except Exception:
                logger.error("Failed to update ScrapeRun %s", run_id)
    finally:
        db.close()