from calendar import monthrange
from datetime import date, datetime, timedelta


FREQUENCIES = {"hebdomadaire": 7, "bimensuelle": 14, "mensuelle": None}


def generate_occurrence_dates(
    frequency: str,
    start: date,
    until: date,
    service_weekdays: set[int],
) -> list[date]:
    if frequency not in FREQUENCIES:
        raise ValueError("Fréquence invalide")
    if until < start:
        return []
    dates = []
    current = start
    while current <= until:
        if current.weekday() in service_weekdays:
            dates.append(current)
            if frequency == "mensuelle":
                month = current.month + 1
                year = current.year + (month - 1) // 12
                month = (month - 1) % 12 + 1
                current = current.replace(
                    day=min(current.day, monthrange(year, month)[1]),
                    month=month,
                    year=year,
                )
                continue
            current += timedelta(days=FREQUENCIES[frequency])
            continue
        current += timedelta(days=1)
    return dates


def occurrence_key(subscription_id: int, scheduled_for: datetime) -> tuple[int, datetime]:
    return subscription_id, scheduled_for


def missing_occurrences(
    subscription_id: int,
    candidates: list[datetime],
    existing: set[tuple[int, datetime]],
) -> list[datetime]:
    return [
        candidate
        for candidate in candidates
        if occurrence_key(subscription_id, candidate) not in existing
    ]


def generate_database_occurrences(conn, start: date, until: date) -> int:
    """Generate future occurrences without changing existing occurrence history."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, p.frequency, s.created_at::date, s.preferred_slot_id,
               COALESCE(sl.weekday, 0), COALESCE(sl.starts_at, TIME '08:00')
        FROM domestic_subscriptions s
        JOIN subscription_plans p ON p.id = s.plan_id
        LEFT JOIN service_slots sl ON sl.id = s.preferred_slot_id
        WHERE s.status = 'active' AND p.active = TRUE
          AND s.created_at::date <= %s
        """,
        (until,),
    )
    subscriptions = cur.fetchall()
    created = 0
    for subscription_id, frequency, subscription_start, slot_id, weekday, starts_at in subscriptions:
        dates = generate_occurrence_dates(
            frequency,
            max(start, subscription_start),
            until,
            {weekday},
        )
        for occurrence_date in dates:
            scheduled_for = datetime.combine(occurrence_date, starts_at)
            cur.execute(
                """
                INSERT INTO collection_occurrences (subscription_id, scheduled_for)
                VALUES (%s, %s)
                ON CONFLICT (subscription_id, scheduled_for) DO NOTHING
                """,
                (subscription_id, scheduled_for),
            )
            created += cur.rowcount
    conn.commit()
    cur.close()
    return created