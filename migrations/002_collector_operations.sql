-- Collector availability and capacity. Safe for databases that already applied 001.
ALTER TABLE users ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS service_area VARCHAR(120);
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_capacity INTEGER NOT NULL DEFAULT 8;
ALTER TABLE users ADD COLUMN IF NOT EXISTS available_weekdays SMALLINT[] NOT NULL DEFAULT ARRAY[0,1,2,3,4,5,6];
ALTER TABLE users ADD COLUMN IF NOT EXISTS language_preference TEXT NOT NULL DEFAULT 'fr';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS client_id UUID;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS address_text TEXT;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS translation_key VARCHAR(120);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS translation_params JSONB NOT NULL DEFAULT '{}'::JSONB;

CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_occurrence_schedule
    ON collection_occurrences(subscription_id, scheduled_for);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_user_client_id
    ON reports(user_id, client_id) WHERE client_id IS NOT NULL;