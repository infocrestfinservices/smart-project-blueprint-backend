from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.purpose_model import Purpose
from schemas.purpose_schema import PurposeResponse

router = APIRouter(prefix="/purposes", tags=["Purposes"])

@router.get("/", response_model=List[PurposeResponse])
def get_purposes(db: Session = Depends(get_db)):
    return db.query(Purpose).all()