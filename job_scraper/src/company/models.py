import uuid
from sqlalchemy import Boolean, Column, ForeignKey, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from src.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # company_url = Column(String(500), nullable=True)
    run_id = Column(String(36), ForeignKey("scrape_runs.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    jobs = relationship("Job", back_populates="company")
    contacts = relationship("Contact", back_populates="company")
    scrape_run = relationship("ScrapeRun", back_populates="companies")