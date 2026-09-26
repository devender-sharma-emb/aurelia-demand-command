"""Append-only audit trail. One JSON object per line, so it can be tailed, diffed and replayed."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, path: str | Path | None = None):
        self.entries: list[dict] = []
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, actor: str, event: str, data: dict | None = None) -> dict:
        entry = dict(seq=len(self.entries) + 1, ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     actor=actor, event=event, data=data or {})
        self.entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def events(self, event: str) -> list[dict]:
        return [e for e in self.entries if e["event"] == event]
