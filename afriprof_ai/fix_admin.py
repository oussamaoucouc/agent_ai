"""
Check and fix the admin user password hash
"""
import os
import sys
from sqlalchemy import create_engine, Column, String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import hashlib
import binascii
import secrets
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

def _hash_password_secure(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

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
        print(f"  Error verifying: {e}")
        return False

def fix_admin():
    target_username = "admin@admin.com"
    target_password = "admin"
    
    engine = create_engine(DB_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print(f"Checking admin user: {target_username}\n")
        
        user = db.query(UserDB).filter(UserDB.username == target_username).first()
        
        if not user:
            print(f"❌ User not found: {target_username}")
            return
        
        print(f"Current user state:")
        print(f"  Username: {user.username}")
        print(f"  User ID: {user.id}")
        print(f"  Role: {user.role}")
        print(f"  Current hash: {user.password_hash}")
        print()
        
        # Test current password
        print(f"Testing current password '{target_password}'...")
        current_valid = _verify_password(target_password, user.password_hash)
        print(f"  Current password valid: {current_valid}")
        print()
        
        # Generate NEW hash
        print(f"Generating new password hash...")
        new_hash = _hash_password_secure(target_password)
        print(f"  New hash: {new_hash}")
        print()
        
        # Verify the new hash works
        print(f"Verifying new hash...")
        new_valid = _verify_password(target_password, new_hash)
        print(f"  New hash valid: {new_valid}")
        print()
        
        if new_valid:
            # Update database
            user.password_hash = new_hash
            db.commit()
            db.refresh(user)
            
            print(f"✅ Password updated in database!")
            print(f"  Updated hash: {user.password_hash}")
            print()
            
            # Final verification
            print(f"Final verification from database...")
            db.expire_all()
            user_check = db.query(UserDB).filter(UserDB.username == target_username).first()
            final_valid = _verify_password(target_password, user_check.password_hash)
            print(f"  Password verification: {final_valid}")
            
            if final_valid:
                print(f"\n✅ SUCCESS! Login credentials:")
                print(f"  Username: {target_username}")
                print(f"  Password: {target_password}")
            else:
                print(f"\n❌ WARNING: Final verification failed!")
        else:
            print(f"❌ ERROR: New hash generation failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_admin()
