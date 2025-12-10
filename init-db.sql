-- PostgreSQL initialization script
-- This runs automatically when the database is first created
-- Ensures the 'ai' and 'rag' schemas exist for all application tables

-- Create extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create ai schema (if not exists)
CREATE SCHEMA IF NOT EXISTS ai;

-- Create rag schema for document metadata
CREATE SCHEMA IF NOT EXISTS rag;

-- Grant permissions on ai schema
GRANT ALL PRIVILEGES ON SCHEMA ai TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT ALL ON TABLES TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT ALL ON SEQUENCES TO ai;

-- Grant permissions on rag schema
GRANT ALL PRIVILEGES ON SCHEMA rag TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag GRANT ALL ON TABLES TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag GRANT ALL ON SEQUENCES TO ai;

-- MinIO columns migration for document_metadata table
-- These columns are added to support MinIO object storage
DO $$
BEGIN
    -- Add minio_bucket_name column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'rag' 
        AND table_name = 'document_metadata' 
        AND column_name = 'minio_bucket_name'
    ) THEN
        ALTER TABLE rag.document_metadata 
        ADD COLUMN minio_bucket_name VARCHAR(128);
    END IF;

    -- Add minio_object_key column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'rag' 
        AND table_name = 'document_metadata' 
        AND column_name = 'minio_object_key'
    ) THEN
        ALTER TABLE rag.document_metadata 
        ADD COLUMN minio_object_key VARCHAR(512);
    END IF;

    -- Add etag column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'rag' 
        AND table_name = 'document_metadata' 
        AND column_name = 'etag'
    ) THEN
        ALTER TABLE rag.document_metadata 
        ADD COLUMN etag VARCHAR(128);
    END IF;
END $$;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Schemas ai and rag initialized successfully';
END $$;
