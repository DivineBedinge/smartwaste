import os
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from database import require_test_database_url
from app.services.notifications import create_notification


@pytest.fixture
def pg_connection():
    try:
        url = require_test_database_url(os.getenv("TEST_DATABASE_URL"))
    except RuntimeError as error:
        pytest.skip(str(error))
    connection = psycopg2.connect(url)
    connection.autocommit = False
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def test_postgis_srid_geometry_and_gist_index(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), PostGIS_Version()")
        database_name, version = cursor.fetchone()
        assert database_name == "smartwaste_test"
        assert version
        cursor.execute("SELECT Find_SRID('public', 'reports', 'geometry')")
        assert cursor.fetchone()[0] == 4326
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname='idx_reports_geometry'")
        assert "gist" in cursor.fetchone()[0].lower()


def test_notification_jsonb_round_trip_uses_psycopg_adapter(pg_connection):
    payload = {"district": "Cité des Palmiers", "danger": "<script>alert(1)</script>"}
    with pg_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users(email,password_hash,role) VALUES (%s,'x','citoyen') RETURNING id",
            (f"json-{uuid4()}@example.test",),
        )
        user_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO notifications(recipient_id,notification_type,title,content,translation_params) VALUES (%s,'test','test','test',%s) RETURNING translation_params",
            (user_id, psycopg2.extras.Json(payload)),
        )
        assert cursor.fetchone()[0] == payload


def test_communication_constraints_and_notification_idempotency(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("INSERT INTO users(email,password_hash,role) VALUES (%s,'x','citoyen') RETURNING id", (f"comms-{uuid4()}@example.test",))
        user_id = cursor.fetchone()[0]
        key = str(uuid4())
        cursor.execute("INSERT INTO notifications(recipient_id,notification_type,title,content,idempotency_key) VALUES (%s,'test','t','c',%s) ON CONFLICT (recipient_id,idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING", (user_id, key))
        cursor.execute("INSERT INTO notifications(recipient_id,notification_type,title,content,idempotency_key) VALUES (%s,'test','t','c',%s) ON CONFLICT (recipient_id,idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING", (user_id, key))
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE recipient_id=%s AND idempotency_key=%s", (user_id, key))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SAVEPOINT callback_constraint")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute("INSERT INTO callback_requests(requester_id,resource_type,reason) VALUES (%s,'report','test')", (user_id,))
        cursor.execute("ROLLBACK TO SAVEPOINT callback_constraint")


def test_notification_outbox_is_atomic_and_deduplicated(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("INSERT INTO users(email,password_hash,role) VALUES (%s,'x','citoyen') RETURNING id", (f"outbox-{uuid4()}@example.test",))
        user_id = cursor.fetchone()[0]
    key = uuid4()
    notification_id = create_notification(pg_connection, user_id, "test", "Test", "Test", idempotency_key=key)
    assert create_notification(pg_connection, user_id, "test", "Test", "Test", idempotency_key=key) == notification_id
    with pg_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM notification_delivery_outbox WHERE notification_id=%s", (notification_id,))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SAVEPOINT outbox_rollback")
    rolled_back_id = create_notification(pg_connection, user_id, "rollback", "Test", "Test", idempotency_key=uuid4())
    with pg_connection.cursor() as cursor:
        cursor.execute("ROLLBACK TO SAVEPOINT outbox_rollback")
        cursor.execute("SELECT COUNT(*) FROM notification_delivery_outbox WHERE notification_id=%s", (rolled_back_id,))
        assert cursor.fetchone()[0] == 0


def test_constraints_foreign_keys_and_idempotency_index_exist(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("SELECT contype, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='reports'::regclass")
        constraints = [(row[0], row[1].lower()) for row in cursor.fetchall()]
        definitions = " ".join(definition for _, definition in constraints)
        assert "foreign key (user_id)" in definitions
        assert any(kind == "c" and "status" in definition for kind, definition in constraints)
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname='uq_reports_user_client_id'")
        assert "unique" in cursor.fetchone()[0].lower()


def test_migration_history_has_ordered_checksums(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("SELECT filename, checksum FROM schema_migrations ORDER BY filename")
        rows = cursor.fetchall()
        assert [row[0] for row in rows] == [
            "001_workflows.sql", "002_collector_operations.sql", "003_collection_cancellation.sql",
            "004_communications.sql",
            "005_notification_outbox.sql",
        ]
        assert all(len(row[1]) == 64 for row in rows)


def test_utf8_seed_text_is_not_corrupted(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("SHOW server_encoding")
        assert cursor.fetchone()[0] == "UTF8"
        cursor.execute("SELECT nom_quartier FROM quartiers_douala WHERE nom_quartier IN (%s,%s,%s)", ("Cité des Palmiers", "Université", "Youpwé"))
        assert {row[0] for row in cursor.fetchall()} == {"Cité des Palmiers", "Université", "Youpwé"}
        cursor.execute("SELECT local_consigne FROM sorting_rules WHERE keyword IN ('pile','plastique')")
        text = " ".join(row[0] for row in cursor.fetchall())
        assert "séparément" in text and "Éviter" in text
        assert "??" not in text and "\ufffd" not in text


def test_invalid_report_status_is_rejected(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("SAVEPOINT invalid_status")
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute("INSERT INTO reports(geometry,status) VALUES (ST_SetSRID(ST_MakePoint(9.7,4.05),4326),'invalid')")
        cursor.execute("ROLLBACK TO SAVEPOINT invalid_status")


def test_assignment_transaction_can_be_rolled_back(pg_connection):
    with pg_connection.cursor() as cursor:
        cursor.execute("INSERT INTO users(email,password_hash,role) VALUES (%s,'x','ramasseur') RETURNING id", (f"collector-{uuid4()}@example.test",))
        collector_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO users(email,password_hash,role) VALUES (%s,'x','citoyen') RETURNING id", (f"citizen-{uuid4()}@example.test",))
        citizen_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO domestic_subscriptions(user_id,address_geometry) VALUES (%s,ST_SetSRID(ST_MakePoint(9.7,4.05),4326)) RETURNING id", (citizen_id,))
        subscription_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO collection_occurrences(subscription_id,scheduled_for) VALUES (%s,NOW()) RETURNING id", (subscription_id,))
        occurrence_id = cursor.fetchone()[0]
        cursor.execute("SAVEPOINT before_assignment")
        cursor.execute("UPDATE collection_occurrences SET collector_id=%s,status='affectee' WHERE id=%s", (collector_id, occurrence_id))
        cursor.execute("ROLLBACK TO SAVEPOINT before_assignment")
        cursor.execute("SELECT collector_id,status FROM collection_occurrences WHERE id=%s", (occurrence_id,))
        assert cursor.fetchone() == (None, "programmee")
