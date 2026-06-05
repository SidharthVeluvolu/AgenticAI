"""Tab 1 — Daily: today's focus, the day's events, and add-event."""

from __future__ import annotations

from datetime import date

import streamlit as st

from .. import storage
from ..components import add_event_button, empty_hint, event_card


def render() -> None:
    day: date = st.session_state.daily_date

    st.markdown(
        f"<h3 style='text-align:center;'>{day.strftime('%A, %B %-d %Y')}</h3>",
        unsafe_allow_html=True,
    )

    # --- Today's focus (persisted per day) ---
    current_focus = storage.get_focus(day)
    focus = st.text_input(
        "Today's focus",
        value=current_focus,
        key="daily_focus_input",
        placeholder="What's the one thing that matters today?",
    )
    if focus != current_focus:
        storage.set_focus(day, focus)

    st.divider()

    # --- Events for the day ---
    events = storage.get_events_for_day(day)
    if events:
        for ev in events:
            event_card(ev, key="daily")
    else:
        empty_hint("No events yet for today.")

    st.write("")
    add_event_button(default_date=day, key="daily")
