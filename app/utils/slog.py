# =============================================
# File: app/utils/slog.py
# Purpose: Minimal structured logging (JSON) + helpers for FastAPI
# =============================================
from __future__ import annotations
import json
import logging
import os
import time
import uuid
import hashlib
from typing import Any, Dict

_LOGGER_NAME = "shakers"
_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_logger = logging.getLogger(_LOGGER_NAME)
if not _logger.handlers:
    _logger.setLevel(getattr(logging, _LEVEL, logging.INFO))
    _handler = logging.StreamHandler()
    # Emit the message as-is; we pre-format JSON strings ourselves
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = True  # allow pytest caplog to capture

def qhash(text: str) -> str:
    """Short hash of a normalized query (for privacy)."""
    norm = " ".join((text or "").strip().lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:10]

def new_request_id() -> str:
    return uuid.uuid4().hex

def log_event(event: str, **fields: Any) -> None:
    rec = {"event": event}
    rec.update(fields)
    _logger.info(json.dumps(rec, ensure_ascii=False))

def finalize_request_log(
    request_id: str,
    method: str,
    path: str,
    status: int,
    latency_ms: int,
    client_ip: str | None,
    ctx: Dict[str, Any] | None = None,
) -> None:
    payload: Dict[str, Any] = {
        "event": "request.completed",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": latency_ms,
        "client_ip": client_ip or "",
    }
    if ctx:
        payload.update(ctx)
    _logger.info(json.dumps(payload, ensure_ascii=False))
