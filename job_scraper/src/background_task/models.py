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
from sqlalchemy import CheckConstraint
from src.database import Base

class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    records_scraped = Column(Integer, default=0, nullable=False)
    exception = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    companies = relationship("Company", back_populates="scrape_run")
    contacts = relationship("Contact", back_populates="scrape_run")
    jobs = relationship("Job", back_populates="scrape_run")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'success', 'failed')",
            name="check_scrape_run_status",
        ),
    )