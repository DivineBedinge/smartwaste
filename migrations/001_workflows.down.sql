-- Reversal for 001_workflows.sql. Execute only after an explicit data backup.
DROP TABLE IF EXISTS support_requests;
DROP TABLE IF EXISTS collection_occurrences;
DROP TABLE IF EXISTS domestic_subscriptions;
DROP TABLE IF EXISTS service_slots;
DROP TABLE IF EXISTS subscription_plans;
DROP TABLE IF EXISTS audit_logs;

ALTER TABLE reports DROP COLUMN IF EXISTS rejection_reason;
ALTER TABLE reports DROP COLUMN IF EXISTS review_reason;
ALTER TABLE reports DROP COLUMN IF EXISTS reviewed_at;
ALTER TABLE reports DROP COLUMN IF EXISTS reviewed_by;
ALTER TABLE reports DROP COLUMN IF EXISTS final_severity;
ALTER TABLE reports DROP COLUMN IF EXISTS initial_severity;
ALTER TABLE reports DROP COLUMN IF EXISTS human_review_required;
ALTER TABLE reports DROP COLUMN IF EXISTS analyzed_at;
ALTER TABLE reports DROP COLUMN IF EXISTS classification_model_version;
ALTER TABLE reports DROP COLUMN IF EXISTS classification_source;