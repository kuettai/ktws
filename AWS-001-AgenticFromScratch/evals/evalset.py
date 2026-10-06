"""Load questions.yaml and fill in the date placeholders."""
import calendar
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).parent
DEFAULT_END_DATE = "2026-09-30"   # data/generate_seed.py default; RstDataStack -c seedEndDate=...


def date_values(end_date: str | None = None) -> dict[str, str]:
    """{end}, {week_start}, {month_start}, {month_end}, {month_label} for a given last day of data."""
    end = date.fromisoformat(end_date or os.environ.get("SEED_END_DATE", DEFAULT_END_DATE))
    last_day = calendar.monthrange(end.year, end.month)[1]
    if end.day == last_day:
        month_start = end.replace(day=1)
    else:  # current month is incomplete: use the previous full month
        month_start = (end.replace(day=1) - timedelta(days=1)).replace(day=1)
    month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
    return {
        "end": end.isoformat(),
        "week_start": (end - timedelta(days=6)).isoformat(),
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "month_label": month_start.strftime("%B %Y"),
    }


def _render(value: Any, values: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in values.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [_render(v, values) for v in value]
    if isinstance(value, dict):
        return {k: _render(v, values) for k, v in value.items()}
    return value


def load_questions(
    path: str | Path = HERE / "questions.yaml",
    *,
    end_date: str | None = None,
    ground_truth: str | Path | None = HERE / "ground_truth.json",
    only: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (questions, personas). Defaults are applied and dates filled in.

    expected_answer is taken from ground_truth.json when the question has none of its own.
    """
    spec = yaml.safe_load(Path(path).read_text())
    defaults = spec.get("defaults", {})
    values = date_values(end_date)
    truth = {}
    if ground_truth and Path(ground_truth).exists():
        truth = json.loads(Path(ground_truth).read_text()).get("answers", {})
    questions = []
    for raw in spec["questions"]:
        if only and raw["id"] not in only:
            continue
        q = {**defaults, **_render(raw, values)}
        q.setdefault("expected_params", {})
        q.setdefault("must_mention", [])
        q.setdefault("must_not_call", [])
        if "expected_answer" not in q and q["id"] in truth:
            q["expected_answer"] = truth[q["id"]]
        questions.append(q)
    return questions, spec.get("personas", {})
