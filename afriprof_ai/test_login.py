"""
Test login credentials directly against the database
"""
import os
import sys
from sqlalchemy import create_engine, Column, String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import hashlib
import binascii
import hmac

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

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith('pbkdf2_sha256$'):
            _, iter_str, salt_hex, hash_hex = stored_hash.split('$', 3)
            iterations = int(iter_str)
            salt = binascii.unhexlify(salt_hex.encode())
            expected = binascii.unhexlify(hash_hex.encode())
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            return hmac.compare_digest(dk, expected)
        # Fallback for legacy SHA-256
        sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return sha256_hash == stored_hash
    except Exception as e:
        print(f"  Error verifying password: {e}")
        return False

def test_login():
    # Test credentials
    test_username = "admin@admin.com"
    test_password = "admin"
    
    engine = create_engine(DB_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print(f"Testing login for: {test_username}\n")
        
        # Get user from database
        user = db.query(UserDB).filter(UserDB.username == test_username).first()
        
        if not user:
            print(f"❌ User '{test_username}' not found in database\n")
            print("Available users:")
            users = db.query(UserDB).all()
            for u in users:
                print(f"  - {u.username} (role: {u.role}, id: {u.id})")
            return
        
        print(f"✓ User found:")
        print(f"  Username: {user.username}")
        print(f"  User ID: {user.id}")
        print(f"  Role: {user.role}")
        print(f"  Password hash: {user.password_hash[:50]}...")
        print()
        
        # Test password verification
        print(f"Testing password: '{test_password}'")
        is_valid = _verify_password(test_password, user.password_hash)
        
        if is_valid:
            print(f"✅ Password verification PASSED!")
            print(f"\nLogin should work with:")
            print(f"  Username: {test_username}")
            print(f"  Password: {test_password}")
        else:
            print(f"❌ Password verification FAILED!")
            print(f"\nThe password '{test_password}' does not match the stored hash.")
            print(f"Hash format: {user.password_hash.split('$')[0] if '$' in user.password_hash else 'SHA256'}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_login()
