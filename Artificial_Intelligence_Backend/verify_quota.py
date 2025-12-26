
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from users import DocumentMetadata, Base, get_user_storage_usage, get_user_file_size_limits
from AI_Agents_Workflows.config import DB_URL

# Setup DB connection
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- Inspecting DocumentMetadata ---")
# Check a few rows
rows = db.query(DocumentMetadata).order_by(DocumentMetadata.id.desc()).limit(5).all()
for row in rows:
    print(f"File: {row.filename}, Type: {row.file_type}, Size: {row.file_size} bytes")

print("\n--- Testing Quota Logic for Users ---")
user_id_rows = db.execute(text("SELECT DISTINCT user_id FROM rag.document_metadata")).fetchall()

for r in user_id_rows:
    uid = r[0]
    print(f"User: {uid}")
    usage = get_user_storage_usage(uid, db)
    limits = get_user_file_size_limits(uid, db)
    print(f"  Usage: {usage}")
    print(f"  Limits: {limits}")
    
    # Simulate a check
    for kind, used in usage.items():
        limit = limits.get(kind, 0)
        print(f"  {kind.upper()}: Used {used}, Limit {limit}. Remaining: {limit - used}")

db.close()
