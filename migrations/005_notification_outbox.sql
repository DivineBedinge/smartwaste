CREATE TABLE IF NOT EXISTS notification_delivery_outbox (
    notification_id BIGINT PRIMARY KEY REFERENCES notifications(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES users(id),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending
    ON notification_delivery_outbox(notification_id) WHERE delivered_at IS NULL;
