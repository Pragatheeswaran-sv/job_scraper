from sqlalchemy.orm import Session
from src.contact.models import Contact
from fastapi import status

from src.config import get_logger

logger = get_logger(__name__)

def create_contact(db: Session, first_name: str | None = None, last_name: str | None = None, email_address: str | None = None, phone_number: str | None = None, contact_url: str | None = None, company_id: str | None = None, run_id: str | None = None) -> Contact:
    try:
        existing = db.query(Contact).filter(Contact.first_name == first_name, Contact.last_name == last_name, Contact.run_id == run_id).first()
        if existing:
            logger.info("Contact already exists, skipping: %s %s", first_name, last_name)
            return {
                "status_code": status.HTTP_409_CONFLICT,
                "message": "Contact already exists"
            }
        contact = Contact(
            first_name = first_name, 
            last_name = last_name, 
            email_address = email_address, 
            phone_number = phone_number, 
            contact_url = contact_url, 
            company_id = company_id, 
            run_id = run_id, 
            is_active = True
        )
        
        db.add(contact)
        db.commit()
        db.refresh(contact)

        logger.info("Contact inserted: %s %s", first_name, last_name)
        return contact.id
        
    except Exception as e:
        logger.error('ERROR in create contact function: %s', e)
        return {
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Error while adding contact"
        }