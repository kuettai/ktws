"""Day 1 Module 02 checkpoint: every Redshift tool you built follows the SQL rules.

    cd mcp-server && uv run pytest tests/test_sql_rules.py -v

Finds the tools defined in tools/redshift_tools.py, calls each one with sample inputs, captures
the SQL instead of running it (no AWS needed), and checks it against kiro/steering/sql-rules.md.
Before Module 02 (no tools/redshift_tools.py yet) the test is skipped.
"""
import asyncio
import importlib
import inspect
import re

import pytest

rt = pytest.importorskip("tools.redshift_tools", reason="no tools/redshift_tools.py yet (Module 02)")
import server  # noqa: E402  registers every tool module that server.py imports

SAMPLE_ARGS = {  # sample value for each parameter name the workshop's tools use
    "branch_id": 12, "start_date": "2026-09-01", "end_date": "2026-09-07",
    "name_fragment": "bayside", "top_n": 5, "day_type": "all", "category": "all",
}


def redshift_tools() -> list[str]:
    """Names of the MCP tools whose function lives in tools/redshift_tools.py."""
    registered = {t.name for t in asyncio.run(server.mcp.list_tools())}
    own = {name for name, fn in inspect.getmembers(rt, inspect.isfunction) if fn.__module__ == rt.__name__}
    return sorted(registered & own)


def test_you_have_built_redshift_tools():
    assert redshift_tools(), "no Redshift tools found: is tools.redshift_tools imported in server.py?"


@pytest.mark.parametrize("tool", redshift_tools() or ["(none yet)"])
def test_sql_follows_the_rules(tool, monkeypatch):
    if tool == "(none yet)":
        pytest.skip("no Redshift tools yet")
    captured = []
    monkeypatch.setattr(rt, "run_query", lambda sql, params=None: captured.append((sql, params or {})) or [])
    schema = next(t.input_schema for t in asyncio.run(server.mcp.list_tools()) if t.name == tool)
    unknown = [p for p in schema.get("properties", {}) if p not in SAMPLE_ARGS]
    if unknown:
        pytest.skip(f"no sample value for parameter(s) {unknown}: add one to SAMPLE_ARGS to check this tool")
    args = {p: SAMPLE_ARGS[p] for p in schema.get("properties", {})}
    asyncio.run(server.mcp.call_tool(tool, args))
    assert captured, f"{tool} did not run a query through run_query"
    sql, params = captured[0]
    flat = " ".join(sql.split())
    assert re.search(r"\bFROM mcp\.v_\w+", flat), "query only the curated mcp.v_* views"
    assert not re.search(r"\brst\.", flat), "never query base tables in schema rst"
    assert "SELECT *" not in flat.upper(), "list the columns you need, no SELECT *"
    assert re.search(r"\bLIMIT \d+\s*$", flat), "end every query with LIMIT <number>"
    for name in params:
        assert f":{name}" in sql, f"pass {name} as a :{name} bind parameter"
    for value in ("2026-09-01", "2026-09-07", "bayside"):
        assert value not in sql, f"the value {value!r} was pasted into the SQL: use a :name parameter"
