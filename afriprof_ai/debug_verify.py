"""
Test the exact _verify_password function from users.py
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

# Import the actual function from users.py
from users import _verify_password, UserDB

def test_verify():
    target_username = "admin@admin.com"
    target_password = "admin"
    
    engine = create_engine(DB_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print(f"Testing password verification for: {target_username}\n")
        
        user = db.query(UserDB).filter(UserDB.username == target_username).first()
        
        if not user:
            print(f"❌ User not found")
            return
        
        print(f"User found:")
        print(f"  Username: {user.username}")
        print(f"  Password hash: {user.password_hash}")
        print()
        
        print(f"Testing password: '{target_password}'")
        print(f"  Length: {len(target_password)} characters")
        print(f"  Bytes: {target_password.encode('utf-8')}")
        print()
        
        # Parse the hash manually
        if user.password_hash.startswith('pbkdf2_sha256$'):
            parts = user.password_hash.split('$')
            print(f"Hash parts:")
            print(f"  Algorithm: {parts[0]}")
            print(f"  Iterations: {parts[1]}")
            print(f"  Salt (hex): {parts[2]}")
            print(f"  Hash (hex): {parts[3]}")
            print()
            
            # Manual verification
            iterations = int(parts[1])
            salt = binascii.unhexlify(parts[2].encode())
            expected = binascii.unhexlify(parts[3].encode())
            
            print(f"Manual verification:")
            print(f"  Salt length: {len(salt)} bytes")
            print(f"  Expected hash length: {len(expected)} bytes")
            
            dk = hashlib.pbkdf2_hmac('sha256', target_password.encode('utf-8'), salt, iterations)
            print(f"  Computed hash length: {len(dk)} bytes")
            print(f"  Computed hash (hex): {binascii.hexlify(dk).decode()}")
            print(f"  Expected hash (hex): {binascii.hexlify(expected).decode()}")
            print(f"  Match: {hmac.compare_digest(dk, expected)}")
            print()
        
        # Use the actual function from users.py
        result = _verify_password(target_password, user.password_hash)
        
        if result:
            print(f"✅ Password verification PASSED using users._verify_password!")
        else:
            print(f"❌ Password verification FAILED using users._verify_password!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_verify()
