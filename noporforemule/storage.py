from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .scanner import MODEL_VERSION, ScanResult


def app_data_dir() -> Path:
    import os
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "NoPorForEmule"


class Settings:
    def __init__(self, base: Path):
        self.path = base / "config.json"

    def load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            try:
                legacy = self.path.parent.parent / "EmuleAviso" / "config.json"
                old = json.loads(legacy.read_text(encoding="utf-8"))
                return {"incoming": old.get("folder", ""), "temp": "", "emule": ""}
            except (OSError, ValueError, TypeError):
                return {}

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class Cache:
    def __init__(self, base: Path):
        base.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(base / "cache.sqlite3")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS scans (path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, "
            "model TEXT, status TEXT, detail TEXT)"
        )

    def get(self, path: Path, size: int, mtime_ns: int) -> ScanResult | None:
        row = self.db.execute(
            "SELECT status, detail FROM scans WHERE path=? AND size=? AND mtime_ns=? AND model=?",
            (str(path), size, mtime_ns, MODEL_VERSION),
        ).fetchone()
        return ScanResult(*row) if row else None

    def put(self, path: Path, size: int, mtime_ns: int, result: ScanResult) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO scans VALUES (?, ?, ?, ?, ?, ?)",
            (str(path), size, mtime_ns, MODEL_VERSION, result.status, result.detail),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()
