import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
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
    job_url = Column(Text, nullable=False, unique=True)

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
    required_skills = relationship("JobRequiredSkill", back_populates="job", cascade="all, delete-orphan")
    preferred_skills = relationship("JobPreferredSkill", back_populates="job", cascade="all, delete-orphan")


class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    required_jobs = relationship("JobRequiredSkill", back_populates="skill")
    preferred_jobs = relationship("JobPreferredSkill", back_populates="skill")

class JobPreferredSkill(Base):
    __tablename__ = "job_preferred_skills"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    skill_id = Column(String(36), ForeignKey("job_skills.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    job = relationship("Job", back_populates="preferred_skills")
    skill = relationship("JobSkill", back_populates="preferred_jobs")

class JobRequiredSkill(Base):
    __tablename__ = "job_required_skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    skill_id = Column(String(36), ForeignKey("job_skills.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    job = relationship("Job", back_populates="required_skills")
    skill = relationship("JobSkill", back_populates="required_jobs")