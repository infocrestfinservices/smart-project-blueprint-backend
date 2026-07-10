from sqlalchemy import Column, Integer, String, Text
from database import Base

class Purpose(Base):
    __tablename__ = "purposes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    best_for = Column(Text, nullable=True)
    recommended_when = Column(Text, nullable=True)
    icon = Column(String, nullable=True)