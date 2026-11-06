"""Pure calendar and command tests; no model, database, or network required."""
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from src.services.ask_genius_periods import (
    Period, parse_question_period, preference_command, resolve_period,
)


@pytest.mark.parametrize("preset,start,end", [
    ("last_7_days", "2026-10-21", "2026-10-27"),
    ("last_14_days", "2026-10-14", "2026-10-27"),
    ("last_30_days", "2026-09-28", "2026-10-27"),
    ("last_month", "2026-09-01", "2026-09-30"),
    ("last_quarter", "2026-07-01", "2026-09-30"),
    ("last_6_months", "2026-04-27", "2026-10-27"),
    ("year_to_date", "2026-01-01", "2026-10-27"),
])
def test_inclusive_calendar_ranges(preset, start, end):
    result = resolve_period(Period(preset=preset), today=date(2026, 10, 27))
    assert result["start_date"] == start
    assert result["end_date"] == end
    assert result["timezone"] == "America/New_York"


def test_year_boundary_leap_year_and_month_clamping():
    assert resolve_period(Period(preset="last_month"), date(2026, 1, 1))["start_date"] == "2025-12-01"
    assert resolve_period(Period(preset="last_quarter"), date(2026, 1, 1))["start_date"] == "2025-10-01"
    assert resolve_period(Period(preset="last_month"), date(2024, 3, 1))["end_date"] == "2024-02-29"
    assert resolve_period(Period(preset="last_6_months"), date(2026, 8, 31))["start_date"] == "2026-02-28"


def test_relative_default_rolls_and_all_history_has_no_bounds():
    period = Period(preset="last_7_days")
    assert resolve_period(period, date(2026, 10, 28))["start_date"] == "2026-10-22"
    assert "start_date" not in resolve_period(Period(preset="all_time"))


@pytest.mark.parametrize("values", [
    {"preset": "custom", "start_date": "2026-10-01"},
    {"preset": "custom", "start_date": "2026-10-27", "end_date": "2026-10-01"},
    {"preset": "custom", "start_date": "2026-02-30", "end_date": "2026-03-01"},
    {"preset": "last_7_days", "start_date": "2026-10-01"},
    {"preset": "all_time", "other": "forbidden"},
    {"preset": "custom", "start_date": datetime(2026, 10, 1), "end_date": "2026-10-27"},
    {"preset": "custom", "start_date": 1790812800, "end_date": "2026-10-27"},
    {"preset": "custom", "start_date": "2026-10-01T00:00:00", "end_date": "2026-10-27"},
])
def test_invalid_periods_are_rejected(values):
    with pytest.raises(ValidationError):
        Period(**values)


def test_custom_bounds_and_future_rejection():
    period = Period(preset="custom", start_date="2026-10-01", end_date="2026-10-27")
    assert resolve_period(period, date(2026, 10, 27))["end_date"] == "2026-10-27"
    with pytest.raises(ValueError, match="on or before today"):
        resolve_period(period, date(2026, 10, 26))


@pytest.mark.parametrize("question,preset", [
    ("What were the complaints in the past seven days?", "last_7_days"),
    ("Show reviews from last week", "last_7_days"),
    ("What happened during the past two weeks?", "last_14_days"),
    ("Use the last 30 days", "last_30_days"),
    ("Show last calendar month", "last_month"),
    ("Which topics occurred last quarter?", "last_quarter"),
    ("What changed in the past six months?", "last_6_months"),
    ("Show year-to-date reviews", "year_to_date"),
    ("What happened YTD?", "year_to_date"),
    ("Look at all available history", "all_time"),
])
def test_explicit_supported_question_periods(question, preset):
    assert parse_question_period(question).preset == preset


def test_iso_range_parsing_and_no_inference():
    period = parse_question_period("Summarize reviews between 2026-09-01 and 2026-09-30")
    assert period.model_dump(mode="json") == {"preset": "custom", "start_date": "2026-09-01", "end_date": "2026-09-30"}
    assert parse_question_period("Show supporting reviews") is None
    assert parse_question_period("Which topics came up during this period?") is None


@pytest.mark.parametrize("question", [
    "Compare last month and the last 30 days",
    "Show past 3 months",
    "What happened since last month?",
    "Reviews before last quarter",
    "Compare this month with last month",
    "Do not use last 30 days",
    "Show all available history except last month",
    "Reviews from 2026-10-01",
    "Review 2026-01-01 to 2026-01-31 and 2026-02-01 to 2026-02-28",
])
def test_ambiguous_or_unsupported_periods_clarify(question):
    with pytest.raises(ValueError):
        parse_question_period(question)


@pytest.mark.parametrize("question", [
    "What complaints came in today?",
    "What about tomorrow?",
    "What happened in the past few days?",
    "Show feedback from the last several weeks",
    "Review the past couple of months",
    "What did residents mention in September?",
    "Summarize Q2 2026",
    "What happened in the second quarter of 2025?",
    "What were complaints in 2025?",
    "What happened since the year 2024?",
    "Compare last month with Q2 2026",
])
def test_other_obvious_timeframes_request_selection(question):
    with pytest.raises(ValueError, match="Please choose one period"):
        parse_question_period(question)


@pytest.mark.parametrize("question", [
    "Did 2026 reviews include complaints?",
    "What did residents say about May?",
    "Explain the rating of 2",
    "Which topics appeared in reviews?",
])
def test_numbers_and_month_names_without_time_context_do_not_set_period(question):
    assert parse_question_period(question) is None


@pytest.mark.parametrize("command", [
    "Use last 30 days as my default going forward.",
    "Last 30 days is my default going forward",
    "Please make the last 30 days my default",
    "Could you please set my default period to last 30 days?",
    "Save last 30 days as my default, from now on",
])
def test_explicit_preference_commands(command):
    action, period = preference_command(command)
    assert action == "save"
    assert period.preset == "last_30_days"


def test_clear_and_current_period_commands():
    assert preference_command("Remove my default") == ("clear", None)
    assert preference_command("Please clear my saved default period.") == ("clear", None)
    assert preference_command("Make this period my default") == ("save", None)


@pytest.mark.parametrize("text", [
    "Show last 7 days",
    "What if I use last 30 days as my default?",
    "Do not make last 30 days my default",
    "I don't want to remove my default",
    "The resident wrote: use last 30 days as my default",
    "Remove my default and summarize maintenance",
    "Last 30 days is my default?",
])
def test_temporaries_hypotheticals_negations_and_embedded_commands_do_not_write(text):
    assert preference_command(text) is None


@pytest.mark.parametrize("text", [
    "Make last 7 days or last 30 days my default",
    "Use not last 30 days as my default",
    "Set my default to yesterday",
])
def test_invalid_preference_command_requests_clarification(text):
    with pytest.raises(ValueError):
        preference_command(text)


@pytest.mark.parametrize("quote", [
    '"I paid yesterday"', '“I paid last month”',
    "'I didn't pay yesterday'", '‘I didn’t pay yesterday’',
    '"The trouble started from 2026-01-01 to 2026-01-31"',
])
def test_quoted_words_are_content_not_date_filters(quote):
    assert parse_question_period(f"Did the 3-month survey mention {quote}?") is None
    assert parse_question_period(f"Which reviews last week mentioned {quote}?").preset == "last_7_days"


@pytest.mark.parametrize("question", [
    "Show yesterday's reviews", "Show yesterday’s survey submissions",
    "Show survey responses submitted yesterday",
    "Which surveys from yesterday mentioned “I paid last month”?",
])
def test_explicit_yesterday_means_previous_property_calendar_day(monkeypatch, question):
    monkeypatch.setattr("src.services.ask_genius_periods.community_today", lambda: date(2026, 1, 1))
    assert parse_question_period(question) == Period(preset="custom", start_date="2025-12-31",
                                                     end_date="2025-12-31")


@pytest.mark.parametrize("question", [
    "Show reviews since yesterday", "Show all history except yesterday’s reviews",
    "Compare yesterday’s surveys and last month", "Show surveys about yesterday’s repairs",
    "How many surveys were not submitted yesterday?", "Show surveys not submitted yesterday",
    "Don’t show maintenance surveys submitted yesterday",
    "What about surveys submitted before yesterday?",
])
def test_relative_day_with_ambiguous_or_conflicting_scope_clarifies(question):
    with pytest.raises(ValueError):
        parse_question_period(question)


@pytest.mark.parametrize("question", [
    "Which residents need a call today?",
    "Can I tell the parking reviewer that we will add spaces next month?",
    "Can we tell residents we plan to repair the elevators next week?",
    "Give me three bullets for tomorrow’s onsite huddle, based on both reviews and surveys.",
])
def test_planning_date_is_not_a_filter_on_review_or_submission_dates(question):
    assert parse_question_period(question) is None
    assert parse_question_period("Using reviews from last week: " + question).preset == "last_7_days"

def test_planned_action_leaves_an_explicit_submission_date_in_force():
    period = parse_question_period("Using surveys submitted yesterday, can I say we will fix the faucet next month?")
    assert period.preset == 'custom'
    with pytest.raises(ValueError):
        parse_question_period("Show surveys due next month")


@pytest.mark.parametrize("phrase,first,last", [
    ("How many reviews have a posting date in November 2026?", "2026-11-01", "2026-11-06"),
    ("Which reviews are we leaving out when we look only at this month?", "2026-11-01", "2026-11-06"),
    ("Did anybody post about parking this month?", "2026-11-01", "2026-11-06"),
    ("Show reviews during the month of October 2026", "2026-10-01", "2026-10-31"),
    ("Show Feb. 2024 surveys", "2024-02-01", "2024-02-29"),
])
def test_explicit_named_reporting_month(monkeypatch, phrase, first, last):
    monkeypatch.setattr("src.services.ask_genius_periods.community_today", lambda: date(2026, 11, 6))
    assert parse_question_period(phrase) == Period(preset='custom', start_date=first, end_date=last)


@pytest.mark.parametrize("question", [
    "With all available history selected, show only our November reviews.",
    "Did we get more reviews in November than in October?",
    "Compare November 2026 with October 2026", "Show reviews in November 2026 and October 2025",
    "Show surveys since October 2026", "Show surveys from October 2026 onward",
    "Show December 2026 reviews", "Which reviews were not posted this month?",
    "Which surveys weren’t submitted in November 2026?",
])
def test_unknown_year_two_periods_or_future_month_clarify(monkeypatch, question):
    monkeypatch.setattr("src.services.ask_genius_periods.community_today", lambda: date(2026, 11, 6))
    with pytest.raises(ValueError):
        parse_question_period(question)


def test_a_quoted_or_planned_month_preserves_selected_period():
    assert parse_question_period('Can I tell residents we will add amenities in November 2026?') is None
    assert parse_question_period('What did the resident mean by “this month”?') is None
