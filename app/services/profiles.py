# =============================================
# File: app/services/profiles.py
# Purpose: User profile store backed by JSON
# =============================================

# app/services/profiles.py
from __future__ import annotations
import json
import os
import threading
from typing import Dict, List, Optional, Set

_PROFILES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "profiles", "profiles.json")

class ProfileStore:
    """
    Minimal user profile store:
    - query_history: recent queries (list[str], capped)
    - seen_resources: set of resource ids/urls already shown in answers/recommendations
    Persistence: JSON file (thread-safe best-effort). If the file/folder doesn't exist, it is created on first write.
    """
    def __init__(self, path: str = _PROFILES_PATH, history_cap: int = 50) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._mem: Dict[str, Dict] = {}
        self._history_cap = history_cap
        self._load()

    def _ensure_dir(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._mem = json.load(f)
        except Exception:
            self._mem = {}

    def _flush(self) -> None:
        self._ensure_dir()
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._mem, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    def _get(self, user_id: str) -> Dict:
        if user_id not in self._mem:
            self._mem[user_id] = {"query_history": [], "seen_resources": []}
        return self._mem[user_id]

    def append_query(self, user_id: str, query: str) -> None:
        with self._lock:
            p = self._get(user_id)
            qh: List[str] = p.get("query_history", [])
            qh.append(query.strip())
            if len(qh) > self._history_cap:
                qh[:] = qh[-self._history_cap :]
            p["query_history"] = qh
            self._flush()

    def add_seen(self, user_id: str, resource_ids: List[str]) -> None:
        if not resource_ids:
            return
        with self._lock:
            p = self._get(user_id)
            seen: Set[str] = set(p.get("seen_resources", []))
            for rid in resource_ids:
                if rid:
                    seen.add(str(rid))
            p["seen_resources"] = sorted(seen)
            self._flush()

    def get_profile(self, user_id: str) -> Dict:
        with self._lock:
            return dict(self._get(user_id))  # shallow copy

# Global instance
PROFILE_STORE = ProfileStore()
