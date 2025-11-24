-- Migration: Add session_media table for multimodal file tracking
-- Created: 2025-11-24

CREATE TABLE IF NOT EXISTS session_media (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('image', 'audio', 'video')),
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add foreign key constraint (assuming sessions table exists)
-- Note: This will cascade delete media when session is deleted
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sessions') THEN
        ALTER TABLE session_media 
        ADD CONSTRAINT fk_session_media_session 
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_session_media_session ON session_media(session_id);
CREATE INDEX IF NOT EXISTS idx_session_media_user ON session_media(user_id);
CREATE INDEX IF NOT EXISTS idx_session_media_type ON session_media(media_type);
CREATE INDEX IF NOT EXISTS idx_session_media_created ON session_media(created_at);

-- Add comment for documentation
COMMENT ON TABLE session_media IS 'Stores metadata for multimodal media files (images, audio, video) attached to chat sessions';
COMMENT ON COLUMN session_media.media_type IS 'Type of media: image, audio, or video';
COMMENT ON COLUMN session_media.file_path IS 'Absolute path to the media file on disk';
COMMENT ON COLUMN session_media.file_size IS 'Size of the file in bytes';
