"""Worker planifie et interruptible pour les automatisations SmartWaste.

Le mode ``--once`` conserve le comportement historique. Le mode boucle est
destine au profil Docker de demonstration et ne demarre jamais sous APP_ENV=test.
"""
from __future__ import annotations

import argparse
import os
import signal
import threading
from collections.abc import Callable

from app.services.automation import run_daily_automation
from database import get_db_connection


def run_once() -> dict:
    connection = get_db_connection()
    try:
        return run_daily_automation(connection)
    finally:
        connection.close()


def run_worker(
    interval_seconds: float,
    *,
    stop_event: threading.Event,
    job: Callable[[], dict] = run_once,
) -> int:
    if os.getenv("APP_ENV", "development").lower() == "test":
        raise RuntimeError("Le worker d'automatisation est desactive pendant les tests")
    if interval_seconds < 30:
        raise ValueError("AUTOMATION_INTERVAL_SECONDS doit etre au moins egal a 30")
    failures = 0
    while not stop_event.is_set():
        try:
            print(job(), flush=True)
            failures = 0
        except Exception as error:
            failures += 1
            print({"status": "failed", "error_type": type(error).__name__}, flush=True)
        delay = min(interval_seconds * max(1, failures), interval_seconds * 5)
        stop_event.wait(delay)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automatisations SmartWaste")
    parser.add_argument("--once", action="store_true", help="Execute une fois puis quitte")
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("AUTOMATION_INTERVAL_SECONDS", "300")),
    )
    args = parser.parse_args(argv)
    if args.once:
        print(run_once())
        return 0
    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    return run_worker(args.interval, stop_event=stop_event)


if __name__ == "__main__":
    raise SystemExit(main())
