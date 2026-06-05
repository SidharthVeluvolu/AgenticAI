"""Tab 2 — Weekly: week navigation, day picker, selected-day detail, add-event."""

from __future__ import annotations

import streamlit as st

from .. import storage
from ..components import add_event_button, empty_hint, event_card
from ..state import shift_week, week_days


def render() -> None:
    anchor = st.session_state.week_anchor
    days = week_days(anchor)
    selected = st.session_state.weekly_selected

    # --- Header with prev/next week arrows ---
    left, mid, right = st.columns([0.1, 0.8, 0.1])
    with left:
        if st.button("‹", key="week_prev", help="Previous week"):
            shift_week(-1)
            st.rerun()
    with mid:
        st.markdown(
            f"<h3 style='text-align:center;'>"
            f"{selected.strftime('%a, %B %-d %Y')}</h3>",
            unsafe_allow_html=True,
        )
    with right:
        if st.button("›", key="week_next", help="Next week"):
            shift_week(1)
            st.rerun()

    # --- Seven day buttons; a dot marks days that have events ---
    cols = st.columns(7)
    week_events = storage.get_events(days[0], days[-1])
    days_with_events = {ev.date for ev in week_events}
    for col, d in zip(cols, days):
        with col:
            is_selected = d == selected
            label = f"{d.strftime('%a')[:2]}\n{d.day}"
            if st.button(
                label,
                key=f"weekday_{d.isoformat()}",
                width="stretch",
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.weekly_selected = d
                st.rerun()
            dot = "●" if d in days_with_events else " "
            st.markdown(
                f"<div style='text-align:center;color:#666;'>{dot}</div>",
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#666;'>Selected day detail</p>",
        unsafe_allow_html=True,
    )

    # --- Events for the selected day ---
    day_events = [ev for ev in week_events if ev.date == selected]
    if day_events:
        for ev in day_events:
            event_card(ev, key="weekly")
    else:
        empty_hint("No events on this day.")

    st.write("")
    add_event_button(default_date=selected, key="weekly")
