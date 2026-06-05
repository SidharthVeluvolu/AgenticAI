"""Session-state initialization and date-navigation helpers.

Streamlit reruns the whole script on every interaction, so any value that must
survive a rerun (the day you're looking at, the week offset, the month being
browsed) lives in ``st.session_state`` and is seeded here once per session.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st


def init_state() -> None:
    """Seed navigation state on first run of a session."""
    today = date.today()
    st.session_state.setdefault("daily_date", today)
    st.session_state.setdefault("week_anchor", today)  # any day inside the week
    st.session_state.setdefault("month_anchor", today.replace(day=1))
    st.session_state.setdefault("weekly_selected", today)
    st.session_state.setdefault("perf_range", "Today")


def week_bounds(anchor: date) -> tuple[date, date]:
    """Return (Monday, Sunday) for the week containing ``anchor``."""
    monday = anchor - timedelta(days=anchor.weekday())
    return monday, monday + timedelta(days=6)


def week_days(anchor: date) -> list[date]:
    """Return the seven dates (Mon..Sun) of the week containing ``anchor``."""
    monday, _ = week_bounds(anchor)
    return [monday + timedelta(days=i) for i in range(7)]


def shift_week(delta: int) -> None:
    """Move the weekly view by ``delta`` weeks and keep the selection in range."""
    st.session_state.week_anchor += timedelta(weeks=delta)
    monday, sunday = week_bounds(st.session_state.week_anchor)
    sel = st.session_state.weekly_selected
    if not (monday <= sel <= sunday):
        st.session_state.weekly_selected = monday


def shift_month(delta: int) -> None:
    """Move the monthly view by ``delta`` months."""
    anchor = st.session_state.month_anchor
    month_index = anchor.year * 12 + (anchor.month - 1) + delta
    year, month = divmod(month_index, 12)
    st.session_state.month_anchor = date(year, month + 1, 1)
