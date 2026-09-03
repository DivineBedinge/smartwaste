DROP INDEX IF EXISTS uq_collection_occurrence_schedule;
ALTER TABLE users DROP COLUMN IF EXISTS available_weekdays;
ALTER TABLE users DROP COLUMN IF EXISTS daily_capacity;
ALTER TABLE users DROP COLUMN IF EXISTS service_area;
ALTER TABLE users DROP COLUMN IF EXISTS active;