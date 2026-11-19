"""
Assignment 11 — Audit Log implementation.

Records every interaction for forensics. Never blocks by itself —
other layers catch attacks; this layer makes them reviewable.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path


def default_audit_log_path() -> str:
    """Always resolve to <repo>/outputs/… (safe when cwd is src/)."""
    repo_root = Path(__file__).resolve().parents[2]
    return str(repo_root / "outputs" / "audit_log.json")


class AuditLogPlugin:
    """Framework-agnostic audit logger (wire into ADK callbacks or your pipeline)."""

    def __init__(self):
        self.name = "audit_log"
        self.logs: list[dict] = []
        self._open: dict[str, tuple] = {}

    def record_input(self, *, user_id: str, text: str, request_id: str | None = None):
        """ store input + start timestamp keyed by request_id/user_id."""
        from guardrails.output_guardrails import content_filter
        key = request_id or user_id
        if key in self._open:
            raise ValueError("An outstanding request needs a unique request_id")
        self._open[key] = (time.monotonic(), utc_now_iso(), content_filter(text)["redacted"])

    def record_output(
        self,
        *,
        user_id: str,
        text: str,
        blocked: bool = False,
        layer: str | None = None,
        request_id: str | None = None,
    ):
        """ store output, layer decision, latency; append to self.logs."""
        from guardrails.output_guardrails import content_filter
        start, timestamp, input_text = self._open.pop(request_id or user_id, (time.monotonic(), utc_now_iso(), ""))
        self.logs.append(dict(user_id=user_id, request_id=request_id, input=input_text,
                              output=content_filter(text)["redacted"], timestamp=timestamp,
                              blocked=blocked, layer=layer, latency_ms=(time.monotonic()-start)*1000))

    def export_json(self, filepath: str | None = None):
        """Write logs to disk (JSON array) under repo-root ``outputs/`` by default."""
        path = Path(filepath or default_audit_log_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.logs, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
