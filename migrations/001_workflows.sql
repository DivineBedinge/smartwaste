-- Additive schema for role-aware workflows, reviews and domestic collection.
-- Run this script on a database backup. Existing tables and rows are preserved.

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    actor_role VARCHAR(32) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id INTEGER,
    old_value JSONB,
    new_value JSONB,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE reports ADD COLUMN IF NOT EXISTS classification_source VARCHAR(32);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS classification_model_version VARCHAR(100);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS human_review_required BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS initial_severity VARCHAR(32);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS final_severity VARCHAR(32);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS reviewed_by INTEGER REFERENCES users(id);
ALTER TABLE reports ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS review_reason TEXT;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

CREATE TABLE IF NOT EXISTS subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    frequency VARCHAR(32) NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    service_area VARCHAR(120),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS service_slots (
    id SERIAL PRIMARY KEY,
    service_area VARCHAR(120) NOT NULL,
    weekday SMALLINT NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS domestic_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    plan_id INTEGER REFERENCES subscription_plans(id),
    address_geometry geometry(Point, 4326) NOT NULL,
    service_area VARCHAR(120),
    preferred_slot_id INTEGER REFERENCES service_slots(id),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('active', 'suspended', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS collection_occurrences (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES domestic_subscriptions(id),
    collector_id INTEGER REFERENCES users(id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'programmee',
    missed_reason VARCHAR(64),
    rescheduled_to INTEGER REFERENCES collection_occurrences(id),
    started_at TIMESTAMPTZ,
    arrived_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('programmee', 'affectee', 'en_route', 'arrivee', 'effectuee', 'confirmee', 'manquee', 'reprogrammee'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_occurrence_schedule
    ON collection_occurrences(subscription_id, scheduled_for);

CREATE TABLE IF NOT EXISTS support_requests (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id),
    author_role VARCHAR(32) NOT NULL,
    category VARCHAR(64) NOT NULL,
    subject VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    attachment_url TEXT,
    priority VARCHAR(16) NOT NULL DEFAULT 'normal',
    status VARCHAR(32) NOT NULL DEFAULT 'ouverte',
    assigned_to INTEGER REFERENCES users(id),
    manager_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (priority IN ('basse', 'normal', 'haute', 'critique')),
    CHECK (status IN ('ouverte', 'en_examen', 'resolue', 'rejetee', 'fermee', 'contestee', 'remise_en_examen'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_occurrences_collector_date ON collection_occurrences(collector_id, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_occurrences_subscription_date ON collection_occurrences(subscription_id, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_support_requests_author ON support_requests(author_id);