import sys
print("Python:", sys.executable)

from database import engine, SessionLocal, Base
print("Database imported OK")

from models.industry_model import Industry
from models.country_model import Country
from models.purpose_model import Purpose
from models.user_model import User
from models.project_model import Project
from models.report_model import Report
from models.questionnaire_model import QuestionnaireAnswer
from models.feasibility_model import FeasibilityScore
print("Models imported OK")

Base.metadata.create_all(bind=engine)
print("Tables created OK")

db = SessionLocal()
if db.query(Industry).count() == 0:
    db.add(Industry(name="Restaurant"))
    db.commit()
    print("Test insert OK")
else:
    print("Data already exists")
db.close()
print("DONE")