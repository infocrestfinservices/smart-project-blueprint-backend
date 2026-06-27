import os

os.makedirs("models", exist_ok=True)

files = {
    "models/industry_model.py": """from sqlalchemy import Column, Integer, String
from database import Base

class Industry(Base):
    __tablename__ = "industries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
""",
    "models/country_model.py": """from sqlalchemy import Column, Integer, String
from database import Base

class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    currency = Column(String, nullable=True)
""",
    "models/purpose_model.py": """from sqlalchemy import Column, Integer, String
from database import Base

class Purpose(Base):
    __tablename__ = "purposes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
""",
    "models/user_model.py": """from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    plan = Column(String, default="starter")
    created_at = Column(DateTime, default=datetime.utcnow)
    projects = relationship("Project", back_populates="user")
""",
    "models/project_model.py": """from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    sub_industry = Column(String, nullable=True)
    country = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    location = Column(String, nullable=True)
    promoter_name = Column(String, nullable=True)
    promoter_experience = Column(String, nullable=True)
    project_description = Column(String, nullable=True)
    target_market = Column(String, nullable=True)
    target_customers = Column(String, nullable=True)
    project_cost = Column(Float, nullable=True)
    own_contribution = Column(Float, nullable=True)
    loan_amount = Column(Float, nullable=True)
    purpose = Column(String, nullable=True)
    government_scheme_name = Column(String, nullable=True)
    report_format = Column(String, nullable=True)
    financial_format = Column(String, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="projects")
    report = relationship("Report", back_populates="project", uselist=False)
    questionnaire = relationship("QuestionnaireAnswer", back_populates="project", uselist=False)
    scores = relationship("FeasibilityScore", back_populates="project", uselist=False)
""",
    "models/report_model.py": """from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    report_content = Column(Text, nullable=True)
    report_format = Column(String, nullable=True)
    financial_format = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="report")
""",
    "models/questionnaire_model.py": """from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class QuestionnaireAnswer(Base):
    __tablename__ = "questionnaire_answers"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    chat_history = Column(Text, nullable=True)
    collected_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="questionnaire")
""",
    "models/feasibility_model.py": """from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text
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
""",
    "models/__init__.py": """from .industry_model import Industry
from .country_model import Country
from .purpose_model import Purpose
from .user_model import User
from .project_model import Project
from .report_model import Report
from .questionnaire_model import QuestionnaireAnswer
from .feasibility_model import FeasibilityScore
""",
}

for path, content in files.items():
    with open(path, "w") as f:
        f.write(content)
    print(f"Created {path}")

print("\nAll files created!")