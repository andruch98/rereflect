"""Validated calendar periods and conservative, local preference commands.

These helpers never inspect source records or call a model. Date filtering uses
original posting dates in the community's calendar, not import timestamps.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

TIMEZONE = "America/New_York"
Preset = Literal[
    "last_7_days", "last_14_days", "last_30_days", "last_month", "last_quarter",
    "last_6_months", "year_to_date", "all_time", "custom",
]


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: Preset
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def require_calendar_date(cls, value):
        if value is None or type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use a calendar date in YYYY-MM-DD format.")
        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.preset == "custom":
            if self.start_date is None or self.end_date is None:
                raise ValueError("Choose both the start and end dates.")
            if self.start_date > self.end_date:
                raise ValueError("The start date must be on or before the end date.")
        elif self.start_date is not None or self.end_date is not None:
            raise ValueError("Only a custom period accepts start and end dates.")
        return self


def community_today() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def _subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def resolve_period(period: Period, today: date | None = None) -> dict:
    """Return an inclusive date range; relative presets roll when resolved."""
    today = today or community_today()
    labels = {
        "last_7_days": "Last 7 days", "last_14_days": "Last 14 days",
        "last_30_days": "Last 30 days", "last_month": "Last month",
        "last_quarter": "Last quarter", "last_6_months": "Last 6 months",
        "year_to_date": "Year to date", "all_time": "All available history",
        "custom": "Custom period",
    }
    result = {"preset": period.preset, "label": labels[period.preset], "timezone": TIMEZONE}
    if period.preset == "all_time":
        return result
    end = today
    if period.preset in {"last_7_days", "last_14_days", "last_30_days"}:
        days = {"last_7_days": 7, "last_14_days": 14, "last_30_days": 30}[period.preset]
        start = today - timedelta(days=days - 1)
    elif period.preset == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif period.preset == "last_quarter":
        this_quarter = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        end = this_quarter - timedelta(days=1)
        start = _subtract_months(this_quarter, 3)
    elif period.preset == "last_6_months":
        start = _subtract_months(today, 6)
    elif period.preset == "year_to_date":
        start = today.replace(month=1, day=1)
    else:
        start, end = period.start_date, period.end_date
        if end > today:
            raise ValueError("Choose an end date on or before today.")
        result["label"] = f"{start.isoformat()} to {end.isoformat()}"
    result.update(start_date=start.isoformat(), end_date=end.isoformat())
    return result


_PERIOD_PATTERNS = [
    ("last_7_days", r"(?:last|past)\s+(?:7|seven)\s+days|(?:last|past)\s+(?:one\s+|1\s+)?week"),
    ("last_14_days", r"(?:last|past)\s+(?:14|fourteen)\s+days|(?:last|past)\s+(?:2|two)\s+weeks"),
    ("last_30_days", r"(?:last|past)\s+(?:30|thirty)\s+days"),
    ("last_month", r"last\s+(?:calendar\s+)?month"),
    ("last_quarter", r"last\s+(?:calendar\s+)?quarter"),
    ("last_6_months", r"(?:last|past)\s+(?:6|six)\s+months"),
    ("year_to_date", r"year[\s-]+to[\s-]+date|ytd|this\s+year"),
    ("all_time", r"all[\s-]+time|all\s+(?:available\s+|saved\s+)?history|entire\s+(?:available\s+)?history"),
]
_DATE_RANGE = r"(?:from\s+|between\s+)?(\d{4}-\d{2}-\d{2})\s*(?:to|through|until|and|[–—])\s*(\d{4}-\d{2}-\d{2})"
_CLARIFY = "Please choose one period, or enter a specific start and end date."
_MONTH_NAMES = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_UNSUPPORTED_TIME_CONTEXT = (
    r"\b(?:today|yesterday|tomorrow)\b"
    r"|\b(?:last|past|previous|next|this)\s+(?:(?:a\s+)?few|several|some|(?:a\s+)?couple(?:\s+of)?)"
    r"\s+(?:days?|weeks?|months?|quarters?|years?)\b"
    r"|\b(?:in|during|since|before|after|through|until|from|for|over)\s+"
    r"(?:(?:the\s+)?month\s+of\s+)?(?:" + _MONTH_NAMES + r")\b"
    r"|\bQ[1-4]\s+(?:19|20)\d{2}\b"
    r"|\b(?:first|second|third|fourth)\s+quarter(?:\s+(?:of\s+)?(?:19|20)\d{2})?\b"
    r"|\b(?:in|during|since|before|after|through|until|from|for)\s+(?:the\s+year\s+)?(?:19|20)\d{2}\b"
)


def parse_question_period(question: str) -> Period | None:
    """Recognize supported explicit periods, refusing ambiguous comparisons."""
    matches: list[tuple[int, int, Period]] = []
    for match in re.finditer(_DATE_RANGE, question, re.IGNORECASE):
        matches.append((match.start(), match.end(), Period(
            preset="custom", start_date=match.group(1), end_date=match.group(2))))
    for preset, pattern in _PERIOD_PATTERNS:
        for match in re.finditer(r"\b(?:" + pattern + r")\b", question, re.IGNORECASE):
            before = question[max(0, match.start() - 60):match.start()].lower()
            if re.search(r"\b(?:before|since|until|earlier\s+than|older\s+than)\s+(?:the\s+)?$", before):
                raise ValueError(_CLARIFY)
            if re.search(
                r"\b(?:not|never|except|excluding|don't|don’t|do\s+not)"
                r"\s+(?:(?:use|show|choose|select|include)\s+)?(?:the\s+)?$", before,
            ):
                raise ValueError(_CLARIFY)
            matches.append((match.start(), match.end(), Period(preset=preset)))

    # An unrecognized explicit timeframe must not silently reuse the old filter.
    remainder = question
    for start, end, _ in sorted(matches, reverse=True, key=lambda item: item[0]):
        remainder = remainder[:start] + " " * (end - start) + remainder[end:]
    if re.search(
        r"\b(?:last|past|this|previous|next)\s+(?:(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s+)?"
        r"(?:days?|weeks?|months?|quarters?|years?)\b|\b\d{4}-\d{2}-\d{2}\b",
        remainder, re.IGNORECASE,
    ) or re.search(_UNSUPPORTED_TIME_CONTEXT, remainder, re.IGNORECASE):
        raise ValueError(_CLARIFY)
    unique = {p.model_dump_json(exclude_none=True): p for _, _, p in matches}
    if len(unique) > 1:
        raise ValueError(_CLARIFY)
    return next(iter(unique.values()), None)


def _preference_period(fragment: str) -> Period | None:
    fragment = fragment.strip().lower()
    fragment = re.sub(r"^the\s+", "", fragment)
    if fragment in {"this period", "current period", "selected period", "currently selected period"}:
        return None
    for preset, pattern in _PERIOD_PATTERNS:
        if re.fullmatch(r"(?:" + pattern + r")", fragment, re.IGNORECASE):
            return Period(preset=preset)
    match = re.fullmatch(_DATE_RANGE, fragment, re.IGNORECASE)
    if match:
        return Period(preset="custom", start_date=match.group(1), end_date=match.group(2))
    raise ValueError("Choose the period you want to save as your default.")


def preference_command(question: str) -> tuple[str, Period | None] | None:
    """Recognize explicit whole-message commands only; return save/clear."""
    asks_confirmation = question.strip().endswith("?")
    text = question.strip().rstrip(".!?").strip()
    text = re.sub(r"^(?:please\s+|(?:can|could|would)\s+you\s+(?:please\s+)?)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,?\s*(?:going\s+forward|from\s+now\s+on)$", "", text, flags=re.IGNORECASE)
    if re.fullmatch(
        r"(?:remove|clear|delete|forget|reset)\s+(?:my|the)\s+(?:saved\s+)?"
        r"(?:(?:time\s*period|period|timeframe)\s+)?default(?:\s+(?:time\s*period|period|timeframe))?",
        text, re.IGNORECASE,
    ):
        return "clear", None
    patterns = [
        r"(?:use|save|set)\s+(.+?)\s+as\s+my\s+default(?:\s+(?:period|timeframe))?",
        r"make\s+(.+?)\s+my\s+default(?:\s+(?:period|timeframe))?",
        r"set\s+my\s+default(?:\s+(?:period|timeframe))?\s+to\s+(.+)",
        r"(.+?)\s+is\s+my\s+default(?:\s+(?:period|timeframe))?",
    ]
    for index, pattern in enumerate(patterns):
        match = re.fullmatch(pattern, text, re.IGNORECASE)
        if match:
            # A statement phrased as a question may be checking the current
            # setting. Imperative requests such as "Could you set ...?" remain
            # supported, but this ambiguous form must not write a preference.
            if index == len(patterns) - 1 and asks_confirmation:
                return None
            return "save", _preference_period(match.group(1))
    return None
