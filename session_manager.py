# session_manager.py
from collections import defaultdict
import time

class SessionManager:
    def __init__(self, timeout_seconds=300):
        self._sessions = {}
        self._timeout = timeout_seconds

    def get_session(self, session_id: str):
        """Récupère une session ou en crée une nouvelle."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "last_types": [],
                "last_question": "",
                "last_response": "",
                "created_at": time.time()
            }
        # Nettoyer les sessions expirées
        now = time.time()
        for sid in list(self._sessions.keys()):
            if now - self._sessions[sid]["created_at"] > self._timeout:
                del self._sessions[sid]
        return self._sessions[session_id]

    def update_session(self, session_id: str, types: list, question: str, response: str):
        session = self.get_session(session_id)
        session["last_types"] = types
        session["last_question"] = question
        session["last_response"] = response
        session["created_at"] = time.time()

session_manager = SessionManager()