import uuid

from sqlalchemy import (
    Boolean,
    Column,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from src.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    min_experience = Column(Float, nullable=True)
    max_experience = Column(Float, nullable=True)

    education_required = Column(Text, nullable=True)
    employment_type = Column(String(100), nullable=True)

    min_salary = Column(Float, nullable=True)
    max_salary = Column(Float, nullable=True)
    currency_type = Column(String(20), nullable=True)
    salary_payment_period = Column(String(50), nullable=True)

    work_type = Column(String(50), nullable=True)
    source = Column(String(100), nullable=False, index=True)
    job_url = Column(Text, nullable=False)
    job_url_id = Column(String(12), nullable=True)

    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    posted_by = Column(String(36), ForeignKey("contacts.id"), nullable=True, index=True)
    run_id = Column(String(36), ForeignKey("scrape_runs.id"), nullable=False, index=True)

    posted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company", back_populates="jobs")
    posted_by_contact = relationship("Contact", back_populates="posted_jobs", foreign_keys=[posted_by])
    scrape_run = relationship("ScrapeRun", back_populates="jobs")
    job_skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")

class Skill(Base):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    
    job_skills = relationship("JobSkill", back_populates="skill")

class JobSkill(Base):
    __tablename__ = "job_skills"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    skill_id = Column(String(36), ForeignKey("skills.id"), nullable=False, index=True)
    skill_type = Column(String(20), nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    job = relationship("Job", back_populates="job_skills")
    skill = relationship("Skill", back_populates="job_skills")
