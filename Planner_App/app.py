"""Daily Planner — Streamlit entry point.

Four tabs (Daily, Weekly, Monthly, Performance) all read and write a single
SQLite store, so an event added in any tab shows up everywhere on the next
rerun.
"""

import sys
from pathlib import Path

import streamlit as st

# Make the ``src`` layout importable when run via ``streamlit run app.py``.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from planner import storage  # noqa: E402
from planner.state import init_state  # noqa: E402
from planner.views import daily, monthly, performance, weekly  # noqa: E402

st.set_page_config(page_title="Daily Planner", page_icon="🗓️", layout="centered")

storage.init_db()
init_state()

st.title("🗓️ Daily Planner")

tab_daily, tab_weekly, tab_monthly, tab_perf = st.tabs(
    ["Daily", "Weekly", "Monthly", "Performance"]
)

with tab_daily:
    daily.render()
with tab_weekly:
    weekly.render()
with tab_monthly:
    monthly.render()
with tab_perf:
    performance.render()
