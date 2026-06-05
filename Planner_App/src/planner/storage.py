"""SQLite persistence layer.

This module is the single source of truth for the whole app. Every tab reads
through these functions, so an event added in one tab automatically appears in
all the others on the next rerun. State lives on disk (``data/planner.db``) so
it survives restarts.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import streamlit as st

from .models import Event

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "planner.db"


@st.cache_resource(show_spinner=False)
def _get_connection() -> sqlite3.Connection:
    """Return a process-wide SQLite connection, creating the schema once.

    Cached with ``cache_resource`` so the same connection is reused across
    Streamlit reruns instead of reopening the file every interaction.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            date           TEXT    NOT NULL,
            time           TEXT    NOT NULL,
            title          TEXT    NOT NULL,
            category       TEXT    NOT NULL,
            duration_hours REAL    NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS focus (
            date TEXT PRIMARY KEY,
            text TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def init_db() -> None:
    """Ensure the database and schema exist (called once at startup)."""
    _get_connection()


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        time=row["time"],
        title=row["title"],
        category=row["category"],
        duration_hours=row["duration_hours"],
    )


# --- Event queries ---------------------------------------------------------

def get_events(start: date, end: date) -> list[Event]:
    """Return events with ``start <= date <= end``, ordered by date then time."""
    conn = _get_connection()
    rows = conn.execute(
        """
        SELECT * FROM events
        WHERE date BETWEEN ? AND ?
        ORDER BY date, time
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [_row_to_event(r) for r in rows]


def get_events_for_day(day: date) -> list[Event]:
    """Return all events on a single day, ordered by time."""
    return get_events(day, day)


def get_all_events() -> list[Event]:
    """Return every event, ordered by date then time."""
    conn = _get_connection()
    rows = conn.execute("SELECT * FROM events ORDER BY date, time").fetchall()
    return [_row_to_event(r) for r in rows]


# --- Event mutations -------------------------------------------------------

def add_event(
    day: date, time: str, title: str, category: str, duration_hours: float
) -> None:
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO events (date, time, title, category, duration_hours)
        VALUES (?, ?, ?, ?, ?)
        """,
        (day.isoformat(), time, title.strip(), category, duration_hours),
    )
    conn.commit()


def delete_event(event_id: int) -> None:
    conn = _get_connection()
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()


# --- Daily focus -----------------------------------------------------------

def get_focus(day: date) -> str:
    conn = _get_connection()
    row = conn.execute(
        "SELECT text FROM focus WHERE date = ?", (day.isoformat(),)
    ).fetchone()
    return row["text"] if row else ""


def set_focus(day: date, text: str) -> None:
    conn = _get_connection()
    text = text.strip()
    if text:
        conn.execute(
            """
            INSERT INTO focus (date, text) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET text = excluded.text
            """,
            (day.isoformat(), text),
        )
    else:
        conn.execute("DELETE FROM focus WHERE date = ?", (day.isoformat(),))
    conn.commit()
