from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    # "free" until something is actually bought. This used to default to "starter", which is
    # the name of the ₹499 plan — so every signup was already on a paid plan and a payment
    # could not be told apart from a registration.
    plan = Column(String, default="free")
    # When a monthly plan lapses. NULL for free and for the one-time Starter, which do not
    # expire. services.entitlements.effective_plan reads this on every request rather than
    # relying on a scheduled job, so an expiry cannot be missed.
    plan_expires_at = Column(DateTime, nullable=True)
    # Staff access to the admin panel. A separate flag rather than a role string because
    # there are exactly two kinds of person here — the team and the customers — and a role
    # table nobody needs is a thing to keep in step for no benefit. Never settable through
    # any API: granted with grant_admin.py, against the database, on purpose.
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    email_verification_otp = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    projects = relationship("Project", back_populates="user")
