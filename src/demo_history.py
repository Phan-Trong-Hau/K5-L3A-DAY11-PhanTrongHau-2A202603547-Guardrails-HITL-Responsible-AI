"""Local SQLite history; only redacted request/response text is persisted."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from guardrails.output_guardrails import content_filter

DEFAULT_PATH = Path(__file__).resolve().parents[1] / '.demo_history' / 'history.sqlite3'


class DemoHistory:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
                target TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                input TEXT NOT NULL, response TEXT NOT NULL,
                blocked INTEGER NOT NULL, layer TEXT, leaked INTEGER NOT NULL)''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def append(self, *, target, provider, model, input, response,
               blocked=False, layer=None, leaked=False):
        with self._connect() as db:
            cursor = db.execute(
                'INSERT INTO history (timestamp,target,provider,model,input,response,blocked,layer,leaked) '
                'VALUES (?,?,?,?,?,?,?,?,?)',
                (datetime.now(timezone.utc).isoformat(), target, provider, model,
                 content_filter(input)['redacted'], content_filter(response)['redacted'],
                 int(blocked), layer, int(leaked)))
            return cursor.lastrowid

    def list(self, limit=20):
        if not 1 <= limit <= 1000:
            raise ValueError('limit must be between 1 and 1000')
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM history ORDER BY id DESC LIMIT ?', (limit,))]

    def clear(self):
        with self._connect() as db:
            db.execute('DELETE FROM history')
