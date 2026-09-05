import threading

import pytest

from automation_worker import run_worker


def test_worker_refuses_test_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    with pytest.raises(RuntimeError, match="desactive"):
        run_worker(30, stop_event=threading.Event(), job=lambda: {})


def test_worker_runs_and_stops_cleanly(monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    stopped = threading.Event()
    calls = []

    def job():
        calls.append(True)
        stopped.set()
        return {"status": "completed"}

    assert run_worker(30, stop_event=stopped, job=job) == 0
    assert len(calls) == 1


def test_worker_rejects_aggressive_interval(monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    with pytest.raises(ValueError, match="30"):
        run_worker(5, stop_event=threading.Event(), job=lambda: {})
