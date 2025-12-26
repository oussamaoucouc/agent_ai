
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from users import DocumentMetadata, Base, get_user_storage_usage
from AI_Agents_Workflows.config import DB_URL

# Setup DB connection
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- Inspecting DocumentMetadata ---")
# Check a few rows to see if file_size is populated
rows = db.query(DocumentMetadata).all()
for row in rows:
    print(f"File: {row.filename}, Type: {row.file_type}, Size: {row.file_size} bytes")

print("\n--- Testing get_user_storage_usage ---")
# Check usage for the first user found or a specific user if known
user_id_rows = db.execute(text("SELECT DISTINCT user_id FROM rag.document_metadata")).fetchall()

for r in user_id_rows:
    uid = r[0]
    print(f"User: {uid}")
    usage = get_user_storage_usage(uid, db)
    print(f"Usage: {usage}")

db.close()
