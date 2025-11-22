-- Initialize PostgreSQL database for Artificial_Intelligence_Backend

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create user 'ai' if it doesn't exist
DO $
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'ai') THEN
        CREATE USER ai WITH PASSWORD 'ai';
    END IF;
END
$;

-- Ensure the database exists
SELECT 'CREATE DATABASE ai' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai')\gexec

-- Grant privileges to the user
GRANT ALL PRIVILEGES ON DATABASE ai TO ai;

-- Connect to the ai database for schema operations
\c ai

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO ai;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ai;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ai;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ai;