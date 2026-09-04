ALTER TABLE collection_occurrences DROP CONSTRAINT IF EXISTS collection_occurrences_status_check;
ALTER TABLE collection_occurrences ADD CONSTRAINT collection_occurrences_status_check CHECK (status IN ('programmee','proposee','affectee','acceptee','refusee','en_route','arrivee','effectuee','en_attente_confirmation','confirmee','contestee','manquee','reprogrammee','annulee'));
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS response_due_at TIMESTAMPTZ;
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS refusal_reason VARCHAR(500);
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS incident_comment VARCHAR(1000);
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS proof_media_asset_id UUID REFERENCES media_assets(id);
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS proof_submitted_at TIMESTAMPTZ;
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS confirmation_due_at TIMESTAMPTZ;
ALTER TABLE collection_occurrences ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS report_transition_history (
 id BIGSERIAL PRIMARY KEY, report_id INTEGER NOT NULL REFERENCES reports(id), actor_id INTEGER REFERENCES users(id),
 actor_role VARCHAR(32), from_status VARCHAR(40), to_status VARCHAR(40) NOT NULL, reason TEXT,
 decision_data JSONB NOT NULL DEFAULT '{}'::JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_report_history ON report_transition_history(report_id,created_at,id);
CREATE TABLE IF NOT EXISTS report_proofs (
 id BIGSERIAL PRIMARY KEY, report_id INTEGER NOT NULL REFERENCES reports(id), agent_id INTEGER NOT NULL REFERENCES users(id),
 media_asset_id UUID NOT NULL REFERENCES media_assets(id), captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, accuracy_m DOUBLE PRECISION, comment VARCHAR(1000),
 status VARCHAR(32) NOT NULL DEFAULT 'soumise' CHECK(status IN ('soumise','en_examen','acceptee','refusee','remplacement_demande')),
 decided_by INTEGER REFERENCES users(id), decision_reason VARCHAR(1000), decided_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_report_proofs_report ON report_proofs(report_id,created_at DESC);
CREATE TABLE IF NOT EXISTS report_disputes (
 id BIGSERIAL PRIMARY KEY, report_id INTEGER NOT NULL REFERENCES reports(id), citizen_id INTEGER NOT NULL REFERENCES users(id),
 reason VARCHAR(64) NOT NULL, comment VARCHAR(2000) NOT NULL, media_asset_id UUID REFERENCES media_assets(id),
 status VARCHAR(24) NOT NULL DEFAULT 'soumise' CHECK(status IN ('soumise','en_examen','confirmee','reouverte','cloturee')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_report_disputes ON report_disputes(report_id,status);
CREATE TABLE IF NOT EXISTS assignment_history (
 id BIGSERIAL PRIMARY KEY, resource_type VARCHAR(20) NOT NULL CHECK(resource_type IN ('report','collection')),
 resource_id INTEGER NOT NULL, assignee_id INTEGER REFERENCES users(id), actor_id INTEGER REFERENCES users(id),
 action VARCHAR(24) NOT NULL CHECK(action IN ('assigned','reassigned','accepted','refused','released')),
 reason VARCHAR(1000), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_assignment_history ON assignment_history(resource_type,resource_id,created_at);
CREATE TABLE IF NOT EXISTS collection_transition_history (
 id BIGSERIAL PRIMARY KEY, occurrence_id INTEGER NOT NULL REFERENCES collection_occurrences(id), actor_id INTEGER REFERENCES users(id),
 actor_role VARCHAR(32), from_status VARCHAR(40), to_status VARCHAR(40) NOT NULL, reason VARCHAR(1000),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS job_runs (
 id BIGSERIAL PRIMARY KEY, job_name VARCHAR(80) NOT NULL, idempotency_key VARCHAR(160) NOT NULL UNIQUE,
 status VARCHAR(20) NOT NULL CHECK(status IN ('running','completed','failed')), result JSONB NOT NULL DEFAULT '{}'::JSONB,
 started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ
);
