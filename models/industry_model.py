from sqlalchemy import Column, Integer, String
from database import Base

class Industry(Base):
    __tablename__ = "industries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
