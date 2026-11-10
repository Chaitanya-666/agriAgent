"""SQLite storage for analysis runs.

One table, `runs`. Each method opens its own short-lived connection: SQLite connections are
cheap, and this keeps the store safe to use from FastAPI's worker threads without sharing a
connection between them. WAL mode lets readers carry on while one request writes.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    filename        TEXT    NOT NULL,
    image_sha256    TEXT    NOT NULL CHECK (length(image_sha256) = 64),
    width           INTEGER NOT NULL CHECK (width > 0),
    height          INTEGER NOT NULL CHECK (height > 0),
    crop            TEXT    NOT NULL,
    mode            TEXT    NOT NULL CHECK (mode IN ('mock', 'real')),
    min_confidence  REAL    NOT NULL CHECK (min_confidence BETWEEN 0.70 AND 1.00),
    safety_action   TEXT    NOT NULL,
    spray_allowed   INTEGER NOT NULL CHECK (spray_allowed IN (0, 1)),
    status          TEXT    NOT NULL,
    weed_count      INTEGER NOT NULL CHECK (weed_count >= 0),
    withheld_count  INTEGER NOT NULL CHECK (withheld_count >= 0),
    infestation_pct REAL    NOT NULL CHECK (infestation_pct BETWEEN 0 AND 100),
    savings_pct     REAL    NOT NULL CHECK (savings_pct BETWEEN 0 AND 100),
    sprayed_px      INTEGER NOT NULL CHECK (sprayed_px >= 0),
    crop_px         INTEGER NOT NULL CHECK (crop_px >= 0),
    unsure_px       INTEGER NOT NULL CHECK (unsure_px >= 0),
    system2_needed  INTEGER NOT NULL CHECK (system2_needed IN (0, 1)),
    duration_ms     REAL    NOT NULL CHECK (duration_ms >= 0),
    geojson         TEXT    NOT NULL,
    overlay_jpeg    BLOB    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs (created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_runs_crop ON runs (crop);
"""

# Columns returned by list/get. The two large columns (geojson, overlay_jpeg) have their own
# methods, so a history page never loads every image.
SUMMARY_COLUMNS = (
    "id, created_at, filename, image_sha256, width, height, crop, mode, min_confidence, "
    "safety_action, spray_allowed, status, weed_count, withheld_count, infestation_pct, "
    "savings_pct, sprayed_px, crop_px, unsure_px, system2_needed, duration_ms"
)

INSERT_COLUMNS = (
    "created_at",
    "filename",
    "image_sha256",
    "width",
    "height",
    "crop",
    "mode",
    "min_confidence",
    "safety_action",
    "spray_allowed",
    "status",
    "weed_count",
    "withheld_count",
    "infestation_pct",
    "savings_pct",
    "sprayed_px",
    "crop_px",
    "unsure_px",
    "system2_needed",
    "duration_ms",
    "geojson",
    "overlay_jpeg",
)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    out = dict(row)
    for flag in ("spray_allowed", "system2_needed"):
        if flag in out:
            out[flag] = bool(out[flag])
    return out


class RunStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def init(self, max_wait_s: float = 10.0) -> None:
        """Create the folder, the table and the indexes if they are missing.

        Several servers may start at the same moment on one new file (load-balanced setup).
        Switching to WAL needs an exclusive lock, and SQLite answers "database is locked" at
        once instead of waiting for the busy timeout, so that one error is retried briefly.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + max_wait_s
        while True:
            try:
                with closing(self._connect()) as conn, conn:
                    if conn.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                        conn.execute("PRAGMA journal_mode = WAL")
                    conn.executescript(SCHEMA)
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)  # another process holds the lock for a few milliseconds

    def ping(self) -> bool:
        try:
            with closing(self._connect()) as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def add(self, run: Dict[str, Any]) -> int:
        missing = [c for c in INSERT_COLUMNS if c not in run]
        if missing:
            raise KeyError(f"run is missing: {', '.join(missing)}")
        values = [run[c] for c in INSERT_COLUMNS]
        placeholders = ", ".join("?" for _ in INSERT_COLUMNS)
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                f"INSERT INTO runs ({', '.join(INSERT_COLUMNS)}) VALUES ({placeholders})", values
            )
            return int(cur.lastrowid)

    def get(self, run_id: int) -> Optional[Dict[str, Any]]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT {SUMMARY_COLUMNS} FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list(
        self, limit: int = 20, offset: int = 0, crop: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Newest first. `crop` filters to one crop when given."""
        where, args = ("WHERE crop = ?", [crop]) if crop else ("", [])
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT {SUMMARY_COLUMNS} FROM runs {where} "
                "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                [*args, limit, offset],
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def count(self, crop: Optional[str] = None) -> int:
        where, args = ("WHERE crop = ?", [crop]) if crop else ("", [])
        with closing(self._connect()) as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM runs {where}", args).fetchone()[0])

    def overlay(self, run_id: int) -> Optional[bytes]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT overlay_jpeg FROM runs WHERE id = ?", (run_id,)).fetchone()
        return bytes(row[0]) if row else None

    def geojson(self, run_id: int) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT geojson FROM runs WHERE id = ?", (run_id,)).fetchone()
        return row[0] if row else None

    def delete(self, run_id: int) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            return cur.rowcount == 1

    def stats(self) -> Dict[str, Any]:
        """Totals for the dashboard, all computed in SQL."""
        with closing(self._connect()) as conn:
            totals = conn.execute(
                """
                SELECT COUNT(*)                                   AS total_runs,
                       COALESCE(SUM(weed_count), 0)               AS total_weeds,
                       COALESCE(SUM(withheld_count), 0)           AS total_withheld,
                       ROUND(COALESCE(AVG(infestation_pct), 0), 2) AS avg_infestation_pct,
                       ROUND(COALESCE(AVG(savings_pct), 0), 2)     AS avg_savings_pct,
                       ROUND(COALESCE(AVG(duration_ms), 0), 2)     AS avg_duration_ms,
                       COALESCE(SUM(spray_allowed = 0), 0)        AS suppressed_runs
                FROM runs
                """
            ).fetchone()
            by_crop = conn.execute(
                """
                SELECT crop, COUNT(*) AS runs, COALESCE(SUM(weed_count), 0) AS weeds,
                       ROUND(AVG(infestation_pct), 2) AS avg_infestation_pct
                FROM runs GROUP BY crop ORDER BY runs DESC, crop
                """
            ).fetchall()
            by_action = conn.execute(
                "SELECT safety_action, COUNT(*) AS runs FROM runs "
                "GROUP BY safety_action ORDER BY runs DESC, safety_action"
            ).fetchall()
        out = dict(totals)
        out["by_crop"] = [dict(r) for r in by_crop]
        out["by_safety_action"] = [dict(r) for r in by_action]
        return out
