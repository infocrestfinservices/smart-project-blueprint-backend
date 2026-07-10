from sqlalchemy import Column, Integer, String
from database import Base

class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    currency = Column(String, nullable=True)
