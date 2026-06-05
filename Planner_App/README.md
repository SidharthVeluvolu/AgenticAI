# 🗓️ Daily Planner

A four-tab daily planner built with Streamlit. Add events once and they show up
across every view, because all tabs read from a single SQLite store.

## Tabs

- **Daily** — set today's focus, see the day's events, add new ones.
- **Weekly** — navigate weeks with ‹ ›, pick any day (including future days),
  and add events to it.
- **Monthly** — full-month calendar with month navigation; days with events are
  marked with a dot, and clicking a day shows what's planned.
- **Performance** — time spent per category (Work, Study, Social, Hobby, Fun,
  Health) for the day / week / month, with scheduled vs. remaining hours against
  a 24h/day budget.

## Run it

```bash
uv run streamlit run app.py
```

The app opens at http://localhost:8501. Data is stored in `data/planner.db`
(created on first run, ignored by git).

## Project layout

```
app.py                     # entry point + tab routing
src/planner/
  models.py                # Event dataclass, categories + colors
  storage.py               # SQLite layer (single source of truth)
  state.py                 # session-state + date navigation
  components.py            # add-event dialog, event cards
  views/                   # one module per tab
.streamlit/config.toml     # theme
data/planner.db            # local SQLite store (gitignored)
```
