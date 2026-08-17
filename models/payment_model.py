from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Payment(Base):
    """One row per attempt, written when the order is created and updated when it is paid.

    A row exists even for an abandoned checkout, which is deliberate: a payment that
    Razorpay took but that never reached us has to be findable afterwards, and it can only
    be found against an order we recorded when we asked for it.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    plan = Column(String, nullable=False)          # starter | professional | enterprise
    # Rupees for reading, paise for reconciling with Razorpay — which only ever talks paise.
    amount = Column(Float, nullable=False)
    amount_paise = Column(Integer, nullable=False)
    currency = Column(String, default="INR")

    razorpay_order_id = Column(String, nullable=False, unique=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)
    razorpay_signature = Column(String, nullable=True)

    # What the customer typed and what it was worth, decided by the SERVER at order time.
    # Kept on the payment because a refund or a GST invoice has to answer "what did they
    # actually pay", and re-deriving it later would give the wrong answer the moment the
    # coupon is edited.
    coupon_code = Column(String, nullable=True)
    discount = Column(Float, default=0.0)

    status = Column(String, default="created")     # created | paid | failed
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User")
