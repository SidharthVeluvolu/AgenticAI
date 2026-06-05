"""Reusable UI pieces shared across tabs: the add-event dialog and event cards."""

from __future__ import annotations

from datetime import date, datetime, time as dtime

import streamlit as st

from . import storage
from .models import CATEGORY_NAMES, DEFAULT_CATEGORY, category_color


@st.dialog("Add event")
def _add_event_dialog(default_date: date, key: str) -> None:
    """Modal form for creating an event on any day (today or future)."""
    with st.form(f"add_event_form_{key}"):
        title = st.text_input("Event name", placeholder="e.g. Team standup")
        col1, col2 = st.columns(2)
        with col1:
            day = st.date_input("Date", value=default_date)
        with col2:
            when = st.time_input("Time", value=dtime(9, 0), step=900)
        col3, col4 = st.columns(2)
        with col3:
            category = st.selectbox(
                "Category",
                CATEGORY_NAMES,
                index=CATEGORY_NAMES.index(DEFAULT_CATEGORY),
            )
        with col4:
            duration = st.number_input(
                "Duration (hours)", min_value=0.25, max_value=24.0,
                value=1.0, step=0.25,
            )
        submitted = st.form_submit_button("Add event", width="stretch")

    if submitted:
        if not title.strip():
            st.warning("Please give the event a name.")
            return
        storage.add_event(
            day=day,
            time=when.strftime("%H:%M"),
            title=title,
            category=category,
            duration_hours=float(duration),
        )
        st.rerun()


def add_event_button(default_date: date, key: str, label: str = "+ add event") -> None:
    """Render a button that opens the add-event dialog prefilled for a date."""
    if st.button(label, key=f"add_btn_{key}", width="stretch"):
        _add_event_dialog(default_date, key)


def event_card(event, key: str) -> None:
    """Render one event as a card with a category accent and a delete button."""
    color = category_color(event.category)
    text_col, del_col = st.columns([0.9, 0.1])
    with text_col:
        st.markdown(
            f"<div style='border-left:4px solid {color};padding:0.35rem 0.6rem;"
            f"background:#fafafa;border-radius:4px;'>"
            f"<span style='font-size:0.95rem;'>{event.summary()}</span></div>",
            unsafe_allow_html=True,
        )
    with del_col:
        if st.button("✕", key=f"del_{key}_{event.id}", help="Delete event"):
            storage.delete_event(event.id)
            st.rerun()


def empty_hint(text: str) -> None:
    """Render a soft, centered placeholder for empty states."""
    st.markdown(
        f"<div style='text-align:center;color:#9e9e9e;padding:1.5rem 0;'>{text}</div>",
        unsafe_allow_html=True,
    )
