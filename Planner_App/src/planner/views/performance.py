"""Tab 4 — Performance: time spent per category vs. the available budget."""

from __future__ import annotations

import calendar
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from .. import storage
from ..components import empty_hint
from ..models import CATEGORIES, CATEGORY_NAMES, HOURS_PER_DAY, category_color
from ..state import week_bounds


def _range_for(choice: str, today: date) -> tuple[date, date, int]:
    """Return (start, end, budget_hours) for the selected range."""
    if choice == "This week":
        start, end = week_bounds(st.session_state.week_anchor)
        return start, end, HOURS_PER_DAY * 7
    if choice == "This month":
        anchor = st.session_state.month_anchor
        days = calendar.monthrange(anchor.year, anchor.month)[1]
        return anchor.replace(day=1), anchor.replace(day=days), HOURS_PER_DAY * days
    return today, today, HOURS_PER_DAY  # Today


def render() -> None:
    today = date.today()

    choice = st.radio(
        "Range",
        ["Today", "This week", "This month"],
        horizontal=True,
        key="perf_range",
        label_visibility="collapsed",
    )
    start, end, budget = _range_for(choice, today)
    events = storage.get_events(start, end)

    # --- Aggregate scheduled hours per category ---
    totals = {name: 0.0 for name in CATEGORY_NAMES}
    for ev in events:
        totals[ev.category] = totals.get(ev.category, 0.0) + ev.duration_hours
    scheduled = sum(totals.values())
    remaining = max(budget - scheduled, 0.0)

    if scheduled == 0:
        empty_hint("No events yet — add some to see your stats.")
        return

    # --- Donut: time spent per category ---
    chart_df = pd.DataFrame(
        [(name, hrs) for name, hrs in totals.items() if hrs > 0],
        columns=["Category", "Hours"],
    )
    donut = (
        alt.Chart(chart_df)
        .mark_arc(innerRadius=70, outerRadius=110)
        .encode(
            theta=alt.Theta("Hours:Q", stack=True),
            color=alt.Color(
                "Category:N",
                scale=alt.Scale(
                    domain=list(CATEGORIES), range=list(CATEGORIES.values())
                ),
                legend=alt.Legend(title="Time spent"),
            ),
            tooltip=["Category", alt.Tooltip("Hours:Q", format=".2f")],
        )
        .properties(height=280)
    )
    st.altair_chart(donut, width="stretch")

    # --- Scheduled / Remaining / Total cards ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Scheduled", f"{scheduled:g} hrs")
    c2.metric("Remaining", f"{remaining:g} hrs")
    c3.metric("Total", f"{budget:g} hrs")

    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#666;'>Category breakdown</p>",
        unsafe_allow_html=True,
    )

    # --- Per-category hours as a horizontal bar ---
    breakdown_df = pd.DataFrame(
        [(name, totals[name]) for name in CATEGORY_NAMES], columns=["Category", "Hours"]
    )
    bars = (
        alt.Chart(breakdown_df)
        .mark_bar()
        .encode(
            x=alt.X("Hours:Q", title="Hours scheduled"),
            y=alt.Y("Category:N", sort=CATEGORY_NAMES, title=None),
            color=alt.Color(
                "Category:N",
                scale=alt.Scale(
                    domain=list(CATEGORIES), range=list(CATEGORIES.values())
                ),
                legend=None,
            ),
            tooltip=["Category", alt.Tooltip("Hours:Q", format=".2f")],
        )
        .properties(height=220)
    )
    st.altair_chart(bars, width="stretch")
