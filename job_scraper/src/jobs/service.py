from datetime import datetime, timezone
from fastapi import status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import asc, desc, func

from src.config import get_logger
from src.database import SessionLocal
from src.jobs.models import Job, JobPreferredSkill, JobRequiredSkill, JobSkill
from src.contact.models import Contact
from src.company.models import Company
from src.scraper.models import ScrapeRun
from src.jobs.schema import JobListResponse, JobSchema

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
            selectinload(Job.required_skills),
            selectinload(Job.preferred_skills),
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


def add_require_and_preferred_skills(db, job_id, skill_id, required=False):
    try:
        if required:
            skill_required = JobRequiredSkill(
                job_id = job_id,
                skill_id = skill_id,
                is_active = True
            )
            db.add(skill_required)
        else:
            skill_preferred = JobPreferredSkill(
                job_id = job_id,
                skill_id = skill_id,
                is_active = True
            )
            db.add(skill_preferred)
    except Exception as e:
        logger.error('Error while inserting skills: %s', e)
        raise

def create_skills(db: Session, job_id: str, required_skills: list, preferred_skills: list):
    try:
        skill_combined = required_skills + preferred_skills
        for skill_name in skill_combined:
            existing = db.query(JobSkill).filter(JobSkill.name == skill_name).first()
            if existing:
                skill_id = existing.id
            else:
                new_skill = JobSkill(name = skill_name, is_active = True)
                db.add(new_skill)
                db.flush()
                skill_id = new_skill.id
                logger.info("Skill inserted: %s", new_skill.name)

            if skill_name in required_skills:
                add_require_and_preferred_skills(db, job_id, skill_id, required=True)
            else:
                add_require_and_preferred_skills(db, job_id, skill_id, required=False)

        db.commit()
        return {
            "status_code": status.HTTP_200_OK,
            "message": "Skills added successfully",
        }
    except Exception as e:
        db.rollback()
        logger.error('Error in create_skills: %s', e)
        return {
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Error while adding skills"
        }