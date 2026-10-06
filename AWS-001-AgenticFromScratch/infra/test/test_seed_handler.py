"""Seed custom resource: when it (re)loads data and when it only refreshes access. No AWS calls.

    uv run --with boto3 --with pytest python -m pytest infra/test -q
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HANDLER = Path(__file__).resolve().parents[1] / "lambda" / "seed" / "handler.py"


@pytest.fixture()
def h(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    spec = importlib.util.spec_from_file_location("seed_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    calls = []
    monkeypatch.setattr(mod, "load_data", lambda props, d: calls.append(("load", d)))
    monkeypatch.setattr(mod, "apply_access", lambda props: calls.append(("access",)))
    mod.calls = calls
    return mod


def event(kind, new, old=None):
    e = {"RequestType": kind, "ResourceProperties": {"SeedEndDate": new}}
    if old is not None:
        e["OldResourceProperties"] = {"SeedEndDate": old}
    return e


def test_create_loads_given_date(h):
    h.on_event(event("Create", "2026-10-05"), None)
    assert h.calls == [("load", "2026-10-05"), ("access",)]


def test_create_without_date_uses_yesterday(h):
    h.on_event(event("Create", ""), None)
    loaded = h.calls[0][1]
    assert len(loaded) == 10 and loaded[4] == "-"


def test_update_without_date_keeps_data(h):            # cdk deploy RstMcpStack, no -c seedEndDate
    h.on_event(event("Update", "", "2026-10-05"), None)
    assert h.calls == [("access",)]


def test_update_same_date_keeps_data(h):               # e.g. only localDevRoleNames changed
    h.on_event(event("Update", "2026-10-05", "2026-10-05"), None)
    assert h.calls == [("access",)]


def test_update_new_date_reloads(h):
    h.on_event(event("Update", "2026-11-01", "2026-10-05"), None)
    assert h.calls == [("load", "2026-11-01"), ("access",)]


@pytest.mark.parametrize("bad", ["20261005", "2026/10/05", "2026-13-01", "yesterday"])
def test_bad_date_rejected(h, bad):
    with pytest.raises(ValueError):
        h.end_date(bad)


def test_delete_does_nothing(h):
    h.on_event({"RequestType": "Delete", "ResourceProperties": {}}, None)
    assert h.calls == []
