# 🗓️ Daily Planner

A four-tab daily planner built with Streamlit. Add an event once and it shows up
across every view — Daily, Weekly, Monthly, and Performance — because all tabs
read from a single SQLite store.

## Tabs

- **Daily** — set today's focus, see the day's events, add new ones.
- **Weekly** — navigate weeks with ‹ ›, pick any day (including future days),
  and add events to it.
- **Monthly** — full-month calendar with month navigation; days with events are
  marked with a dot, and clicking a day shows what's planned.
- **Performance** — time spent per category (Work, Study, Social, Hobby, Fun,
  Health) for the day / week / month, with a donut chart and scheduled vs.
  remaining hours against a 24h/day budget.

## Run it

```bash
uv run streamlit run app.py
```

The app opens at http://localhost:8501. Data is stored in `data/planner.db`
(created on first run, ignored by git).

---

## Thought process & design

This section is the "why" behind the build — the constraint that shaped the
architecture, and the decisions that fell out of it.

### The constraint that drove everything: Streamlit reruns top-to-bottom

Streamlit's execution model is the single most important thing to understand
here. **On every interaction — every click, every keystroke in an input —
Streamlit re-executes the entire script from the top.** There are no event
handlers in the traditional sense; the UI is a pure function of state, re-run
each time.

That one fact dictates the whole design:

1. **State can't live in local variables**, because they're recreated on every
   rerun. Anything that must survive an interaction lives either in
   `st.session_state` (in-memory, per session) or on disk (SQLite).
2. **Cross-tab sync becomes nearly free** — *if* there's a single source of
   truth. Since all four tabs re-render from the same store on every rerun,
   there is no syncing code to write. Add an event in the Weekly tab and it's
   already in the database; the next rerun re-reads it everywhere. This is the
   core requirement ("an event added in one tab shows up in the others"), and
   it's satisfied by architecture rather than by wiring tabs together.

### One source of truth: a thin SQLite layer

Everything funnels through [`storage.py`](src/planner/storage.py). It owns a
single `data/planner.db` file with two tables:

- `events(id, date, time, title, category, duration_hours)`
- `focus(date, text)` — one focus note per day

Every other part of the app is **derived** from the events table by filtering:

| Tab         | Derivation                                                |
|-------------|-----------------------------------------------------------|
| Daily       | events where `date == selected day`                       |
| Weekly      | events in the selected Mon–Sun range                      |
| Monthly     | events grouped by date (to draw the dots)                 |
| Performance | events grouped by category, durations summed             |

**Why SQLite over a JSON file or session-only state?** JSON would have worked
for a single local user, but SQLite gives real queries (date-range filters
instead of loading everything and filtering in Python), durability across
restarts, and a clean upgrade path if this ever grows to multiple users. The
connection is cached with `@st.cache_resource` so it's opened once and reused
across reruns rather than reconnecting on every interaction.

### Tabs without programmatic navigation

The four tabs use plain `st.tabs()`, which matches the mockup exactly and is the
simplest option. The trade-off: you can't *programmatically* jump tabs (e.g.
click a calendar day and auto-switch to Daily). The requirements don't need
that, so the simpler primitive won. If click-through navigation were needed
later, the swap would be to a `st.segmented_control` router driven by
`st.session_state`.

### Navigation state lives in `st.session_state`

Because of the rerun model, "which week am I looking at" and "which day did I
click" have to persist explicitly. [`state.py`](src/planner/state.py) seeds
these once per session (`daily_date`, `week_anchor`, `month_anchor`,
`weekly_selected`, …) and provides the date math (`week_bounds`, `shift_week`,
`shift_month`). Views read and update these keys; the ‹ › arrows just nudge an
anchor date and call `st.rerun()`.

### Performance math

Time spent is the sum of `duration_hours` per category over the selected range.
"Remaining" is computed against a simple budget:

- **Today** → 24 h
- **This week** → 24 × 7 = 168 h
- **This month** → 24 × (days in month)

So `Remaining = max(budget − Scheduled, 0)`. The donut (an Altair arc) shows the
split across categories; a horizontal bar gives the per-category breakdown.
**Altair was chosen over Plotly** because it ships *inside* Streamlit — no extra
dependency — and suits the clean, minimal aesthetic.

### Categories

A fixed, ordered set with stable colors (defined once in
[`models.py`](src/planner/models.py)): **Work, Study, Social, Hobby, Fun,
Health**. Keeping them centralized means the same color is used on event-card
accents, the donut, and the breakdown bar.

### A few Streamlit gotchas handled along the way

- **Unique widget keys.** Every tab renders on every run, so widgets are
  namespaced per view (e.g. `add_btn_weekly` vs `add_btn_daily`) to avoid
  duplicate-key collisions.
- **Modal add-event form.** The "+ add event" button opens a real `st.dialog`
  modal, reused by Daily, Weekly, and Monthly with the date prefilled per tab.
- **Mutate-then-rerun.** After any write (add/delete event, set focus), the code
  calls `st.rerun()` so every tab re-reads the store and reflects the change.

### Known simplifications / future ideas

- Single local user, no authentication.
- "Remaining" uses a flat 24h/day budget rather than configurable waking hours.
- Editing an event = delete + re-add (no in-place edit form yet).
- Categories are fixed; a settings panel could make them user-editable.

---

## Project layout

```
app.py                     # entry point: page config, init, tab routing
src/planner/
  models.py                # Event dataclass, categories + colors, constants
  storage.py               # SQLite layer (single source of truth)
  state.py                 # session-state init + date navigation helpers
  components.py            # add-event dialog, event cards, empty states
  views/
    daily.py               # Tab 1 — Daily
    weekly.py              # Tab 2 — Weekly
    monthly.py             # Tab 3 — Monthly
    performance.py         # Tab 4 — Performance
.streamlit/config.toml     # theme
data/planner.db            # local SQLite store (gitignored)
```

## Tech stack

- **Python 3.12**, managed with [uv](https://docs.astral.sh/uv/)
- **Streamlit** — UI and rerun-based state model
- **Altair** — charts on the Performance tab (bundled with Streamlit)
- **pandas** — shaping data for the charts
- **SQLite** (stdlib `sqlite3`) — local persistence
