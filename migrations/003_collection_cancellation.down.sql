UPDATE collection_occurrences SET status = 'reprogrammee' WHERE status = 'annulee';
ALTER TABLE collection_occurrences DROP CONSTRAINT IF EXISTS collection_occurrences_status_check;
ALTER TABLE collection_occurrences ADD CONSTRAINT collection_occurrences_status_check
    CHECK (status IN ('programmee', 'affectee', 'en_route', 'arrivee', 'effectuee', 'confirmee', 'manquee', 'reprogrammee'));
UPDATE notifications SET translation_params = '{}'::JSONB WHERE translation_params IS NULL;
ALTER TABLE notifications ALTER COLUMN translation_params SET NOT NULL;
