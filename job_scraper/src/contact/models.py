import uuid

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
)

from sqlalchemy.orm import relationship

from src.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(255), nullable=True, index=True)
    last_name = Column(String(255), nullable=True, index=True)
    email_address = Column(String(255), nullable=True, index=True)
    phone_number = Column(String(20), nullable=True, index=True)
    contact_url = Column(String(500), nullable=True)

    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    run_id = Column(String(36), ForeignKey("scrape_runs.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    company = relationship("Company", back_populates="contacts")
    posted_jobs = relationship("Job", back_populates="posted_by_contact")
    scrape_run = relationship("ScrapeRun", back_populates="contacts")