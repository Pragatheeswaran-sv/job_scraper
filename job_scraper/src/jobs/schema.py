from pydantic import BaseModel
from datetime import datetime


class CompanySchema(BaseModel):
    id: str
    name: str
    location: str | None = None
    description: str | None = None
    run_id: str

    class Config:
        from_attributes = True


class ContactSchema(BaseModel):
    id: str
    first_name: str | None = None
    last_name: str | None = None
    email_address: str | None = None
    phone_number: str | None = None
    contact_url: str | None = None
    company_id: str | None = None
    run_id: str

    class Config:
        from_attributes = True


class JobSkillSchema(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True


class JobRequiredSkillSchema(BaseModel):
    id: str
    skill: JobSkillSchema

    class Config:
        from_attributes = True


class JobPreferredSkillSchema(BaseModel):
    id: str
    skill: JobSkillSchema

    class Config:
        from_attributes = True


class JobSchema(BaseModel):
    id: str
    title: str
    location: str | None = None
    description: str | None = None
    min_experience: float | None = None
    max_experience: float | None = None
    education_required: str | None = None
    employment_type: str | None = None
    min_salary: float | None = None
    max_salary: float | None = None
    currency_type: str | None = None
    salary_payment_period: str | None = None
    work_type: str | None = None
    source: str
    job_url: str
    company_id: str | None = None
    posted_by: str | None = None
    run_id: str
    posted_at: datetime | None = None
    company: CompanySchema | None = None
    posted_by_contact: ContactSchema | None = None
    required_skills: list[JobRequiredSkillSchema] = []
    preferred_skills: list[JobPreferredSkillSchema] = []

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    status_code: int
    message: str
    data: list[JobSchema]
    total_records: int
    record_retrieved: int
    page: int
    per_page: int
