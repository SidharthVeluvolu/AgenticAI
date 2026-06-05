"""Tab 3 — Monthly: full-month calendar, month navigation, per-day detail."""

from __future__ import annotations

import calendar
from datetime import date

import streamlit as st

from .. import storage
from ..components import add_event_button, empty_hint, event_card
from ..state import shift_month

_WEEKDAY_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
_CAL = calendar.Calendar(firstweekday=6)  # weeks start on Sunday


def render() -> None:
    anchor: date = st.session_state.month_anchor
    today = date.today()

    # --- Header with prev/next month arrows ---
    left, mid, right = st.columns([0.1, 0.8, 0.1])
    with left:
        if st.button("‹", key="month_prev", help="Previous month"):
            shift_month(-1)
            st.rerun()
    with mid:
        st.markdown(
            f"<h3 style='text-align:center;'>{anchor.strftime('%B %Y')}</h3>",
            unsafe_allow_html=True,
        )
    with right:
        if st.button("›", key="month_next", help="Next month"):
            shift_month(1)
            st.rerun()

    # --- Which days in this month have events ---
    weeks = _CAL.monthdatescalendar(anchor.year, anchor.month)
    month_events = storage.get_events(weeks[0][0], weeks[-1][-1])
    days_with_events = {ev.date for ev in month_events}

    # --- Weekday header row ---
    header_cols = st.columns(7)
    for col, label in zip(header_cols, _WEEKDAY_LABELS):
        col.markdown(
            f"<div style='text-align:center;color:#666;font-weight:600;'>{label}</div>",
            unsafe_allow_html=True,
        )

    selected = st.session_state.get("monthly_selected")

    # --- Calendar grid ---
    for week in weeks:
        cols = st.columns(7)
        for col, d in zip(cols, week):
            with col:
                in_month = d.month == anchor.month
                if not in_month:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    continue
                marker = " ●" if d in days_with_events else ""
                is_today = d == today
                label = f"{'(' if is_today else ''}{d.day}{')' if is_today else ''}{marker}"
                if st.button(
                    label,
                    key=f"monthday_{d.isoformat()}",
                    width="stretch",
                    type="primary" if d == selected else "secondary",
                ):
                    st.session_state.monthly_selected = d
                    st.rerun()

    st.caption("● = has events   ·   ( ) = today")
    st.divider()

    # --- Detail for the day clicked in the grid ---
    if selected and selected.month == anchor.month:
        st.markdown(
            f"<p style='text-align:center;color:#666;'>"
            f"Planned for {selected.strftime('%A, %B %-d')}</p>",
            unsafe_allow_html=True,
        )
        day_events = [ev for ev in month_events if ev.date == selected]
        if day_events:
            for ev in day_events:
                event_card(ev, key="monthly")
        else:
            empty_hint("Nothing planned this day.")
        st.write("")
        add_event_button(default_date=selected, key="monthly")
    else:
        empty_hint("Pick a day to see what's planned.")
