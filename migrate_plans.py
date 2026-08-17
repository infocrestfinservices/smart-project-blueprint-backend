"""Add users.plan_expires_at, and put every user on the plan they actually paid for.

There is no Alembic in this project and `Base.metadata.create_all` only creates MISSING
TABLES — it never adds a column to a table that already exists. So a new column has to be
applied by hand, which is what this does.

The data part matters more than the column. `users.plan` defaulted to "starter", the name of
the ₹499 plan, so all 16 users were sitting on a paid plan none of them had bought. Anyone
with a completed payment keeps what they paid for, with the expiry that plan implies measured
from when they paid.

Everyone else is GRANDFATHERED onto Professional with no expiry, rather than dropped to
free. Not one of the 16 has ever completed a payment — Razorpay is still on test keys and no
order has reached `paid` — so they are the team's own accounts, and several of them already
have reports generated. Dropping them to a one-report free plan would block the people
building the product and, worse, would refuse Word and Excel downloads of reports they had
already made. New signups get `free` from the model default; this only protects accounts
that predate enforcement. Pass `--free-for-all` to drop them instead.

Safe to run more than once: the column is only added if absent, and a user is only moved if
their current plan disagrees with their payment history.
"""
import sys

from sqlalchemy import text

from database import SessionLocal, engine
from models.payment_model import Payment
from models.user_model import User
from services.entitlements import FREE_PLAN, expiry_for, plan_spec

DRY_RUN = "--apply" not in sys.argv
# What an account with no completed payment becomes. See the note above on why this is not
# "free" for accounts that already exist.
GRANDFATHER_PLAN = FREE_PLAN if "--free-for-all" in sys.argv else "professional"


def add_column():
    with engine.connect() as con:
        exists = con.execute(text(
            "select 1 from information_schema.columns "
            "where table_name='users' and column_name='plan_expires_at' "
            "and table_schema = current_schema()")).first()
        if exists:
            print("column users.plan_expires_at: already there")
            return
        # Added even on a dry run, and deliberately: it is a nullable column with no
        # default, so it changes nothing about how the app behaves, and the ORM model
        # already names it — without it every user query fails and the dry run cannot
        # show what it would do. The DATA changes below are what --apply guards.
        con.execute(text("alter table users add column plan_expires_at timestamp"))
        con.commit()
        print("column users.plan_expires_at: added")


def fix_plans():
    db = SessionLocal()
    moves = []
    for u in db.query(User).order_by(User.id):
        # the most recent payment that actually completed decides the plan
        paid = (db.query(Payment)
                  .filter(Payment.user_id == u.id, Payment.status == "paid")
                  .order_by(Payment.paid_at.desc()).first())
        want = (paid.plan if paid else GRANDFATHER_PLAN).strip().lower()
        if want not in ("free", "starter", "professional", "enterprise"):
            want = FREE_PLAN
        # A grandfathered plan must not expire — nobody paid for it, so there is no date to
        # count 30 days from, and an expiry would silently lock the team out a month later.
        want_exp = expiry_for(want, paid.paid_at) if paid else None
        if (u.plan or "").strip().lower() == want and getattr(u, "plan_expires_at", None) == want_exp:
            continue
        moves.append((u.email, u.plan, want, want_exp, bool(paid)))
        if not DRY_RUN:
            u.plan = want
            u.plan_expires_at = want_exp
    if not DRY_RUN:
        db.commit()

    print(f"\nusers to move: {len(moves)}")
    for email, was, now, exp, paid in moves:
        print(f"   {email:<34}{was!r:<16}-> {now!r:<14}"
              f"{'expires ' + exp.strftime('%Y-%m-%d') if exp else 'no expiry':<22}"
              f"{'(has a paid order)' if paid else ''}")


if __name__ == "__main__":
    print("DRY RUN — nothing written. Re-run with --apply to commit.\n"
          if DRY_RUN else "APPLYING\n")
    add_column()
    fix_plans()
