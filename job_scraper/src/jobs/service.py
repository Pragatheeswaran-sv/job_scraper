from datetime import datetime, timezone
from fastapi import status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import asc, desc, func
from datetime import datetime, timedelta
from src.config import get_logger
from src.database import SessionLocal
from src.jobs.models import Job, Skill, JobSkill
from src.contact.models import Contact
from src.company.models import Company
from src.background_task.models import ScrapeRun
from src.jobs.schema import JobListResponse, JobSchema
import pandas as pd
from pathlib import Path
import os
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()

logger = get_logger(__name__)

ALLOWED_FILTER_COLUMNS = ("title", "location", "employment_type", "work_type", "source", "company_id", "currency_type", "education_required", "salary_payment_period", "min_experience", "max_experience", "min_salary", "max_salary")
ALLOWED_SORT_COLUMNS = ("title", "location", "created_at", "updated_at", "min_salary", "max_salary", "posted_at", "employment_type", "work_type", "min_experience", "max_experience")
FLOAT_FIELDS = ("min_experience", "max_experience", "min_salary", "max_salary")

def get_posted_jobs(page, per_page, filter_column, filter_value, sort_column, sort_by):
    try:
        db = SessionLocal()

        query = db.query(Job).options(
            selectinload(Job.company),
            selectinload(Job.posted_by_contact),
            selectinload(Job.job_skills).selectinload(JobSkill.skill)
        )
        if filter_column and filter_value and filter_column in ALLOWED_FILTER_COLUMNS:
            if filter_column in FLOAT_FIELDS:
                try:
                    numeric_value = float(filter_value)
                except ValueError:
                    return {
                        "status_code": 400,
                        "message": "Invalid filter value",
                        "errors": [{"field": "filter_value", "error_message": f"filter_value must be a number for {filter_column}"}]
                    }
                query = query.filter(getattr(Job, filter_column) == numeric_value)
            else:
                query = query.filter(getattr(Job, filter_column).ilike(f"%{filter_value}%"))


        if sort_column and sort_column in ALLOWED_SORT_COLUMNS:
            order = asc(getattr(Job, sort_column)) if sort_by == "asc" else desc(getattr(Job, sort_column))
            query = query.order_by(order)

        total = query.count()
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        if page > total_pages:
            return {
                "status_code": 400,
                "message": "Page exceeds total records",
                "errors": [{"field": "page", "error_message": f"page {page} exceeds total pages {total_pages}"}]
            }
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()
        jobs_data = [JobSchema.model_validate(j) for j in jobs]

        return JobListResponse(
            status_code=status.HTTP_200_OK,
            message="Jobs retrieved successfully",
            data=jobs_data,
            total_records=total,
            record_retrieved= len(jobs_data),
            page=page,
            per_page=per_page,
        )
    
    except Exception as e:
        logger.error('Error while retrieving job posted: %s', e)
        return {
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Error while retrieving job posted"
        }
    finally:
        db.close()


def create_skills(db: Session, job_id: str, required_skills: list, preferred_skills: list):
    try:
        for skill_name in required_skills + preferred_skills:
            existing = db.query(Skill).filter(Skill.name == skill_name).first()
            if existing:
                skill_id = existing.id
            else:
                new_skill = Skill(name=skill_name, is_active=True)
                db.add(new_skill)
                db.flush()
                skill_id = new_skill.id
                logger.info("Skill inserted: %s", new_skill.name)

            skill_type = "required" if skill_name in required_skills else "preferred"
            job_skill = JobSkill(
                job_id=job_id,
                skill_id=skill_id,
                skill_type=skill_type,
                is_active=True,
            )
            db.add(job_skill)

        db.commit()
        return {"status_code": 200, "message": "Skills added successfully"}
    except Exception as e:
        db.rollback()
        logger.error("Error in create_skills: %s", e)
        return {"status_code": 500, "message": "Error while adding skills"}


def send_csv_email(file_path: str, client_email: str):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    cc_emails = os.getenv("CC_EMAILS")

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    message = EmailMessage()

    message["From"] = smtp_username
    message["To"] = client_email
    message["Cc"] = cc_emails
    message["Subject"] = "Today Scraped Jobs Report"

    message.set_content(
        "Hi,\n\n"
        "Please find attached today’s scraped jobs report.\n\n"
        "Regards,\n"
        "Job Scraper"
    )

    with open(file_path, "rb") as file:
        message.add_attachment(
            file.read(),
            maintype="text",
            subtype="csv",
            filename=file_path.name
        )

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)

        logger.info(
            "CSV email sent successfully to %s",
            client_email
        )

        return {
            "status": "success",
            "message": "CSV email sent successfully",
            "recipient": client_email,
            "file": file_path.name
        }

    except Exception:
        logger.exception("Failed to send CSV email")
        raise

def export_scraped_jobs():
    db = SessionLocal()

    try:
        today = datetime.now().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
        tomorrow = today + timedelta(days=1)

        jobs = (
            db.query(Job)
            .options(
                selectinload(Job.company),
                selectinload(Job.posted_by_contact),
                selectinload(Job.job_skills).selectinload(JobSkill.skill)
            )
            .filter(
                Job.created_at >= today,
                Job.created_at < tomorrow
            )
            .all()
        )

        records = []

        for job in jobs:
            company = job.company
            contact = job.posted_by_contact

            # record = {
            #     "id": job.id,
            #     "title": job.title,
            #     "location": job.location,
            #     "employment_type": job.employment_type,
            #     "work_type": job.work_type,
            #     # "description": job.description,
            #     "education_required": job.education_required,
            #     "min_experience": job.min_experience,
            #     "max_experience": job.max_experience,
            #     "min_salary": job.min_salary,
            #     "max_salary": job.max_salary,
            #     "currency_type": job.currency_type,
            #     "salary_payment_period": job.salary_payment_period,
            #     "job_url_id": job.job_url_id,
            #     "job_url": job.job_url,
            #     "posted_at": job.posted_at,
            #     "company_name": company.name if company else "",
            #     "company_description": company.description if company else "",
            #     "company_location": company.location if company else "",
            #     "contact_person_last_name": contact.last_name if contact else "",
            #     "contact_person_phone_number": contact.phone_number if contact else None,
            #     "contact_person_first_name": contact.first_name if contact else "",
            #     "contact_person_email_address": contact.email_address if contact else None,
            #     "contact_person_contact_url": contact.contact_url if contact else "",
            #     "source": job.source,
            #     "created_at": job.created_at,
            # }

            record = {
                "title": job.title,
                # "location": job.location,
                "employment_type": job.employment_type,
                "work_type": job.work_type,
                "min_experience": job.min_experience,
                "max_experience": job.max_experience,
                "job_url": job.job_url,
                "company_name": company.name if company else "",
                # "company_location": company.location if company else "",
                "contact_person_email_address": contact.email_address if contact else None,
                "contact_person_contact_url": contact.contact_url if contact else "",
            }

            records.append(record)

        df = pd.DataFrame(records)

        export_dir = Path("exports")
        export_dir.mkdir(parents=True, exist_ok=True)

        file_path = export_dir / f"jobs_{today.strftime('%Y-%m-%d')}.csv"

        df.to_csv(file_path, index=False, encoding="utf-8-sig")

        # return {
        #     "file_path": str(file_path),
        #     "total_jobs": len(records)
        # }

        client_email = os.getenv("CLIENT_EMAIL")

        email_result = send_csv_email(
            file_path=str(file_path),
            client_email=client_email
        )

        return {
            "total_jobs": len(records),
            "file_path": str(file_path),
            "email": email_result
        }

    except Exception:
        logger.exception("Error exporting scraped jobs")
        raise

    finally:
        db.close()