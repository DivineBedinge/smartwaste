CREATE TABLE IF NOT EXISTS media_assets (
    id UUID PRIMARY KEY,
    storage_key VARCHAR(96) NOT NULL UNIQUE,
    uploader_id INTEGER NOT NULL REFERENCES users(id),
    purpose VARCHAR(40) NOT NULL CHECK (purpose IN ('report_initial','report_proof','collection_proof','dispute_photo','support_attachment','message_attachment')),
    resource_type VARCHAR(32), resource_id INTEGER,
    mime_type VARCHAR(32) NOT NULL CHECK (mime_type IN ('image/jpeg','image/png','image/webp')),
    extension VARCHAR(8) NOT NULL CHECK (extension IN ('.jpg','.png','.webp')),
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
    width INTEGER NOT NULL CHECK (width > 0), height INTEGER NOT NULL CHECK (height > 0),
    sha256 CHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'temporary' CHECK (status IN ('temporary','active','deleted','orphaned')),
    retention_until TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), deleted_at TIMESTAMPTZ,
    CHECK ((resource_type IS NULL) = (resource_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_media_resource ON media_assets(resource_type,resource_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_media_sha256 ON media_assets(sha256,mime_type,size_bytes);
CREATE INDEX IF NOT EXISTS idx_media_temporary ON media_assets(created_at) WHERE status='temporary';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS initial_media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS proof_media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_check;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_content_check;
ALTER TABLE messages ADD CONSTRAINT messages_content_check CHECK (body IS NOT NULL OR attachment_base64 IS NOT NULL OR media_asset_id IS NOT NULL);
ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS media_asset_id UUID REFERENCES media_assets(id);
