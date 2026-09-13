"""
database.py — SQLite-based history, logging, and undo for sort_OCD.

Replaces the brittle flat-text log. Every move is stored in a relational
structure that enables: session-based undo, stats queries, history views.

DB location: ~/.sort_ocd.db
"""

import os
import sqlite3
import datetime
from typing import List, Optional, Tuple

DB_PATH = os.path.expanduser("~/.sort_ocd.db")


def _connect() -> sqlite3.Connection:
    """Open a connection and ensure tables exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist (idempotent)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL,
            target_dir  TEXT NOT NULL,
            sort_mode   TEXT NOT NULL,
            total_moved INTEGER DEFAULT 0,
            source      TEXT DEFAULT 'manual'
        );

        CREATE TABLE IF NOT EXISTS moves (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL,
            src_path    TEXT NOT NULL,
            dest_path   TEXT NOT NULL,
            moved_at    TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    conn.commit()


# ─── Session Management ───────────────────────────────────────────────────────

def create_session(target_dir: str, sort_mode: str, source: str = "manual") -> int:
    """Start a new session. Returns the session ID."""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sessions (started_at, target_dir, sort_mode, source) VALUES (?, ?, ?, ?)",
        (datetime.datetime.now().isoformat(), target_dir, sort_mode, source),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def close_session(session_id: int, total_moved: int) -> None:
    """Mark a session as complete with the final file count."""
    conn = _connect()
    conn.execute(
        "UPDATE sessions SET total_moved = ? WHERE id = ?",
        (total_moved, session_id),
    )
    conn.commit()
    conn.close()


def log_move(session_id: int, src_path: str, dest_path: str) -> None:
    """Record a single file move in the database."""
    conn = _connect()
    conn.execute(
        "INSERT INTO moves (session_id, src_path, dest_path, moved_at) VALUES (?, ?, ?, ?)",
        (session_id, src_path, dest_path, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


# ─── Undo ─────────────────────────────────────────────────────────────────────

def get_last_session_id() -> Optional[int]:
    """Return the ID of the most recent session, or None if no history."""
    conn = _connect()
    row = conn.execute(
        "SELECT id FROM sessions WHERE total_moved > 0 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def get_moves_for_session(session_id: int) -> List[Tuple[str, str]]:
    """Return [(src, dest), ...] for all moves in a session."""
    conn = _connect()
    rows = conn.execute(
        "SELECT src_path, dest_path FROM moves WHERE session_id = ? ORDER BY id DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [(r["src_path"], r["dest_path"]) for r in rows]


def delete_session_moves(session_id: int) -> None:
    """Remove move records after a successful undo (keeps session row for history)."""
    conn = _connect()
    conn.execute("DELETE FROM moves WHERE session_id = ?", (session_id,))
    conn.execute("UPDATE sessions SET total_moved = 0 WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """
    Return aggregated stats for the stats dashboard:
    - total_sessions: all-time session count
    - total_files: all-time files moved
    - recent_sessions: last 5 sessions with details
    - top_modes: most used sort modes
    """
    conn = _connect()

    total_sessions = conn.execute(
        "SELECT COUNT(*) as c FROM sessions WHERE total_moved > 0"
    ).fetchone()["c"]

    total_files = conn.execute(
        "SELECT COALESCE(SUM(total_moved), 0) as s FROM sessions"
    ).fetchone()["s"]

    recent = conn.execute(
        """SELECT id, started_at, target_dir, sort_mode, total_moved, source
           FROM sessions ORDER BY id DESC LIMIT 5"""
    ).fetchall()

    top_modes = conn.execute(
        """SELECT sort_mode, COUNT(*) as count FROM sessions
           GROUP BY sort_mode ORDER BY count DESC LIMIT 5"""
    ).fetchall()

    conn.close()

    return {
        "total_sessions": total_sessions,
        "total_files": total_files,
        "recent_sessions": [dict(r) for r in recent],
        "top_modes": [dict(r) for r in top_modes],
    }


def get_all_sessions(limit: int = 20) -> List[dict]:
    """Return last N sessions for display."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
