-- Collector availability and capacity. Safe for databases that already applied 001.
ALTER TABLE users ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS service_area VARCHAR(120);
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_capacity INTEGER NOT NULL DEFAULT 8;
ALTER TABLE users ADD COLUMN IF NOT EXISTS available_weekdays SMALLINT[] NOT NULL DEFAULT ARRAY[0,1,2,3,4,5,6];

CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_occurrence_schedule
    ON collection_occurrences(subscription_id, scheduled_for);