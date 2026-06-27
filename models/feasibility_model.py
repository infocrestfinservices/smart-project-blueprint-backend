from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class FeasibilityScore(Base):
    __tablename__ = "feasibility_scores"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    feasibility_score = Column(Float, nullable=True)
    bankability_score = Column(Float, nullable=True)
    investment_score = Column(Float, nullable=True)
    risk_score = Column(String, nullable=True)
    swot_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="scores")
