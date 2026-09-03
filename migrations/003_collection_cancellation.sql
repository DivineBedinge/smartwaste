ALTER TABLE collection_occurrences DROP CONSTRAINT IF EXISTS collection_occurrences_status_check;
ALTER TABLE collection_occurrences ADD CONSTRAINT collection_occurrences_status_check
    CHECK (status IN ('programmee', 'affectee', 'en_route', 'arrivee', 'effectuee', 'confirmee', 'manquee', 'reprogrammee', 'annulee'));
ALTER TABLE notifications ALTER COLUMN translation_params DROP NOT NULL;
