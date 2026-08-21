from sqlalchemy.orm import Session
from src.company.models import Company
from fastapi import status

from src.config import get_logger

logger = get_logger(__name__)

def create_company(db: Session, name: str, run_id: str, location: str | None = None, description: str | None = None) -> Company:
    try:
        existing = db.query(Company).filter(Company.name == name).first()
        if existing:
            logger.info("Company already exists, skipping: %s", name)
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "meassage": "Company already exists"
            }
        
        company = Company(name=name, location=location, description=description, run_id=run_id, is_active=True)
        db.add(company)
        db.commit()
        db.refresh(company)

        logger.info("Company inserted: %s", name)
        return {
            "status_code": status.HTTP_200_OK,
            "meassage": "Company added successfully",
            "data": {
                "company_name": name,
            }
        }
    except Exception as e:
            logger.error('ERROR in create company function: ', e)
            return {
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error while adding company"
            }