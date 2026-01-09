#!/usr/bin/env python3
"""Quick diagnostic script to check RAG tables"""
from AI_Agents_Workflows import config as cfg
from sqlalchemy import create_engine, text

engine = create_engine(cfg.VECTOR_DB_URL)
with engine.connect() as conn:
    # List all tables in rag schema
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'rag' 
        ORDER BY table_name
    """))
    tables = [row[0] for row in result]
    print(f"Tables in 'rag' schema: {tables}")
    
    # Check combined_documents table for hashes
    for table in tables:
        if 'combined' in table or 'docling' in table or 'csv' in table:
            try:
                r = conn.execute(text(f"""
                    SELECT COUNT(*), COUNT(DISTINCT meta_data->>'file_sha256')
                    FROM rag."{table}"
                """))
                row = r.fetchone()
                print(f"  {table}: {row[0]} rows, {row[1]} unique hashes")
            except Exception as e:
                print(f"  {table}: ERROR - {e}")
