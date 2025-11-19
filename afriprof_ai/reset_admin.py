"""
Quick script to reset the admin user password in the database.
This will update the existing admin user with the correct password hash.
"""
import os
import sys
from sqlalchemy import create_engine, Column, String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import hashlib
import binascii
import secrets

# Import from your config
sys.path.insert(0, os.path.dirname(__file__))
from teacher_agent.config import DB_URL

Base = declarative_base()

class UserDB(Base):
    __tablename__ = "app_users"
    id = Column(String(64), primary_key=True)
    username = Column(String(256), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="user")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('username', name='uq_app_users_username'),
    )

def _hash_password_secure(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def reset_admin_password():
    # Update the old admin user to new credentials
    old_username = "adi@admin.com"  # Current username in DB
    new_username = "admin@admin.com"  # New username
    new_password = "admin"  # New password to set
    
    engine = create_engine(DB_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Find user with old username
        user = db.query(UserDB).filter(UserDB.username == old_username).first()
        if user:
            user.username = new_username
            user.password_hash = _hash_password_secure(new_password)
            db.commit()
            print(f"✓ User updated successfully!")
            print(f"  Username: {new_username}")
            print(f"  Password: {new_password}")
            print(f"  User ID: {user.id}")
            print(f"  Role: {user.role}")
        else:
            # Check if admin@admin.com already exists
            user = db.query(UserDB).filter(UserDB.username == new_username).first()
            if user:
                # Just update password
                user.password_hash = _hash_password_secure(new_password)
                db.commit()
                print(f"✓ Password reset successfully for user: {new_username}")
                print(f"  New password: {new_password}")
                print(f"  User ID: {user.id}")
                print(f"  Role: {user.role}")
            else:
                print(f"✗ User '{old_username}' not found in database")
                print("\nAvailable users:")
                users = db.query(UserDB).all()
                for u in users:
                    print(f"  - {u.username} (role: {u.role}, id: {u.id})")
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Resetting admin user password...\n")
    reset_admin_password()
