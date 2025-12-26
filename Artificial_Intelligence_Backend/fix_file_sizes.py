
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
from users import DocumentMetadata
from AI_Agents_Workflows.config import DB_URL

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- Fixing Missing File Sizes ---")

# Find docs with 0 size
docs = db.query(DocumentMetadata).filter(DocumentMetadata.file_size == 0).all()
updated_count = 0

for doc in docs:
    if os.path.exists(doc.file_path):
        try:
            size = os.path.getsize(doc.file_path)
            if size > 0:
                print(f"Updating {doc.filename}: 0 -> {size} bytes")
                doc.file_size = size
                updated_count += 1
            else:
                print(f"Skipping {doc.filename}: File on disk is also 0 bytes.")
        except Exception as e:
            print(f"Error reading {doc.file_path}: {e}")
    else:
        print(f"Warning: File not found on disk: {doc.file_path}")

if updated_count > 0:
    db.commit()
    print(f"Successfully updated {updated_count} documents.")
else:
    print("No documents updated.")

db.close()
