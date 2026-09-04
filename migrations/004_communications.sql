ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS resource_type VARCHAR(32);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS resource_id INTEGER;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS idempotency_key UUID;
CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_recipient_idempotency
    ON notifications(recipient_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_notifications_page
    ON notifications(recipient_id, created_at DESC, id DESC);

ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS resource_type VARCHAR(32);
ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS resource_id INTEGER;
ALTER TABLE support_requests ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;
ALTER TABLE support_requests DROP CONSTRAINT IF EXISTS support_requests_status_check;
ALTER TABLE support_requests ADD CONSTRAINT support_requests_status_check CHECK (
    status IN ('ouverte','en_examen','resolue','rejetee','fermee','contestee','remise_en_examen',
               'soumise','reponse_envoyee','rouverte','cloturee')
);
ALTER TABLE support_requests DROP CONSTRAINT IF EXISTS support_requests_category_check;
ALTER TABLE support_requests ADD CONSTRAINT support_requests_category_check CHECK (
    category IN ('collecte_manquee','comportement','erreur_affectation','adresse_inaccessible',
                 'danger','panne','preuve_contestee','probleme_technique','suggestion','autre')
);
CREATE INDEX IF NOT EXISTS idx_support_resource ON support_requests(resource_type, resource_id);

CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    resource_type VARCHAR(32) NOT NULL CHECK (resource_type IN ('report','collection','tour','support')),
    resource_id INTEGER NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(16) NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    UNIQUE(resource_type, resource_id)
);

CREATE TABLE IF NOT EXISTS conversation_participants (
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(conversation_id, user_id),
    FOREIGN KEY(conversation_id, user_id)
        REFERENCES conversation_participants(conversation_id, user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INTEGER REFERENCES users(id),
    client_id UUID NOT NULL,
    message_type VARCHAR(16) NOT NULL DEFAULT 'text' CHECK (message_type IN ('text','image','system')),
    body TEXT,
    attachment_base64 TEXT,
    attachment_mime VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (body IS NOT NULL OR attachment_base64 IS NOT NULL),
    UNIQUE(conversation_id, client_id)
);
CREATE INDEX IF NOT EXISTS idx_messages_page ON messages(conversation_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS conversation_reads (
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS message_reports (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages(id),
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(message_id, reporter_id)
);

CREATE TABLE IF NOT EXISTS callback_requests (
    id BIGSERIAL PRIMARY KEY,
    requester_id INTEGER NOT NULL REFERENCES users(id),
    resource_type VARCHAR(32) CHECK (resource_type IN ('report','collection','tour','support')),
    resource_id INTEGER,
    preferred_at TIMESTAMPTZ,
    reason VARCHAR(500) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested','scheduled','completed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((resource_type IS NULL) = (resource_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_callbacks_status ON callback_requests(status, created_at DESC);
