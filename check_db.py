from database import SessionLocal
from models.user_model import User

def check_users():
    db = SessionLocal()
    users = db.query(User).all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}, Verified: {u.is_verified}, OTP: {u.email_verification_otp}")
    db.close()

if __name__ == '__main__':
    check_users()
