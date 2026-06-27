from database import engine, SessionLocal, Base
from models.industry_model import Industry
from models.country_model import Country
from models.purpose_model import Purpose
from models.user_model import User
from models.project_model import Project
from models.report_model import Report
from models.questionnaire_model import QuestionnaireAnswer
from models.feasibility_model import FeasibilityScore

def init():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created")

    db = SessionLocal()

    if db.query(Industry).count() == 0:
        for name in [
            "Restaurant", "Manufacturing", "Healthcare",
            "Real Estate", "SaaS", "E-commerce",
            "Education", "Logistics", "Data Center",
            "Agriculture", "Retail", "AI Startup"
        ]:
            db.add(Industry(name=name))
        print("✅ Industries seeded")

    if db.query(Country).count() == 0:
        countries = [
            ("India", "INR"), ("USA", "USD"),
            ("UK", "GBP"), ("Australia", "AUD"),
            ("Canada", "CAD"), ("UAE", "AED"),
            ("Germany", "EUR"), ("Singapore", "SGD"),
        ]
        for name, currency in countries:
            db.add(Country(name=name, currency=currency))
        print("✅ Countries seeded")

    if db.query(Purpose).count() == 0:
        for name in [
            "Bank Loan", "Feasibility Study",
            "Government Grant", "Venture Capital",
            "Angel Investment", "Immigration Business Plan"
        ]:
            db.add(Purpose(name=name))
        print("✅ Purposes seeded")

    db.commit()
    db.close()
    print("✅ Database ready")

init()