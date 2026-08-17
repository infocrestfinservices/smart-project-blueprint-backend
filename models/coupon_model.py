from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer, String)
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Coupon(Base):
    """A discount code.

    The code is the only thing the customer ever sends. Everything that decides what it is
    worth — the percentage, the plans it applies to, whether it has run out — lives here, on
    the server. A coupon whose value arrived from the browser would let anyone type their own
    discount into the console, and the payment would still verify perfectly, because Razorpay
    signs whatever amount it was asked to charge.
    """
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    # Stored upper-cased and stripped; matching is done on the normalised form so "  save20 "
    # and "SAVE20" are the same coupon rather than two misses.
    code = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)

    kind = Column(String, nullable=False, default="percent")   # percent | flat
    value = Column(Float, nullable=False)                      # 20 => 20% or ₹20 by kind

    # Empty means every paid plan. Otherwise a comma-separated list of plan keys, so a code
    # can be issued for Professional without also discounting Enterprise.
    applies_to = Column(String, nullable=True)

    # A coupon with no limits is a coupon that ends up on a deals site and is redeemed
    # thousands of times. Both limits are optional, and both are checked at redemption, not
    # only at preview.
    max_redemptions = Column(Integer, nullable=True)
    per_user_limit = Column(Integer, nullable=True, default=1)
    used_count = Column(Integer, nullable=False, default=0)

    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    created_by = Column(String, nullable=True)       # the admin's email, for the audit trail
    created_at = Column(DateTime, default=datetime.utcnow)


class CouponRedemption(Base):
    """One row per actual use, written only when a payment has been VERIFIED.

    Recorded at verification rather than at checkout on purpose: an abandoned checkout must
    not consume a limited coupon, or a handful of people opening and closing the window would
    exhaust a code nobody ever redeemed.
    """
    __tablename__ = "coupon_redemptions"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)

    plan = Column(String, nullable=False)
    # All three are kept. The discount alone cannot be recomputed later if the coupon is
    # edited afterwards, and "what did this customer actually pay" is the question a refund
    # or a GST invoice has to answer.
    original_amount = Column(Float, nullable=False)
    discount = Column(Float, nullable=False)
    final_amount = Column(Float, nullable=False)

    redeemed_at = Column(DateTime, default=datetime.utcnow)

    coupon = relationship("Coupon")
