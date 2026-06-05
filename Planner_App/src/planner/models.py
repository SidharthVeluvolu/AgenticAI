"""Domain models and shared constants for the planner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

# Ordered categories shown across the app. The color is used for the
# Performance charts and the small accents on event cards.
CATEGORIES: dict[str, str] = {
    "Work": "#4C78A8",
    "Study": "#F58518",
    "Social": "#54A24B",
    "Hobby": "#B279A2",
    "Fun": "#E45756",
    "Health": "#72B7B2",
}

CATEGORY_NAMES: list[str] = list(CATEGORIES)

DEFAULT_CATEGORY = "Work"

# Hours available in a single day. Week/month budgets scale from this.
HOURS_PER_DAY = 24


def category_color(name: str) -> str:
    """Return the accent color for a category, defaulting to grey."""
    return CATEGORIES.get(name, "#9E9E9E")


@dataclass(frozen=True)
class Event:
    """A single planned event, owned by exactly one calendar day."""

    id: int
    date: date
    time: str  # "HH:MM" in 24h form; sorts lexicographically
    title: str
    category: str
    duration_hours: float

    @property
    def time_label(self) -> str:
        """Human 12h label, e.g. '9:00 AM'."""
        try:
            return datetime.strptime(self.time, "%H:%M").strftime("%-I:%M %p")
        except ValueError:
            return self.time

    @property
    def duration_label(self) -> str:
        """Compact duration label, e.g. '1hr' or '1.5hr'."""
        hours = self.duration_hours
        text = f"{hours:g}"
        return f"{text}hr"

    def summary(self) -> str:
        """One-line label like '9:00 AM · Team standup · Work · 1hr'."""
        return f"{self.time_label} · {self.title} · {self.category} · {self.duration_label}"
