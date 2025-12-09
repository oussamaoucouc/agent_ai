-- PostgreSQL initialization script
-- This runs automatically when the database is first created
-- Ensures the 'ai' schema exists for all application tables

-- Create the ai schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS ai;

-- Grant all privileges on the ai schema to the ai user
GRANT ALL PRIVILEGES ON SCHEMA ai TO ai;

-- Set default privileges for future tables in the ai schema
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT ALL ON TABLES TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT ALL ON SEQUENCES TO ai;

-- Create the rag schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS rag;

-- Grant all privileges on the rag schema to the ai user
GRANT ALL PRIVILEGES ON SCHEMA rag TO ai;

-- Set default privileges for future tables in the rag schema
ALTER DEFAULT PRIVILEGES IN SCHEMA rag GRANT ALL ON TABLES TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag GRANT ALL ON SEQUENCES TO ai;

-- Ensure pgvector extension is enabled (ankane/pgvector should handle this, but just in case)
CREATE EXTENSION IF NOT EXISTS vector;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Schema ai initialized successfully';
END $$;
