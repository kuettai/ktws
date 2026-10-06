import re

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import server
from tests.conftest import call_tool

RANGE = {"start_date": "2026-09-01", "end_date": "2026-09-07"}
BRANCH_TOOLS = ["get_daily_branch_sales", "get_top_items", "get_peak_hours", "get_channel_mix",
                "get_waste_by_item", "compare_weekend_weekday"]


@pytest.mark.parametrize("tool", BRANCH_TOOLS + ["get_top_branches", "find_branch"])
def test_sql_follows_rules(tool, queries):
    args = {"name_fragment": "central plaza"} if tool == "find_branch" else {**RANGE}
    if tool in BRANCH_TOOLS:
        args["branch_id"] = 12
    call_tool(server.mcp, tool, args)
    sql = queries[0]["sql"]
    assert re.search(r"\bFROM mcp\.v_", sql)
    assert "rst." not in sql
    assert "SELECT *" not in sql
    assert re.search(r"LIMIT \d+\s*$", sql.strip())
    for name in queries[0]["params"]:
        assert f":{name}" in sql, f"{name} must be passed as a bind parameter"
    assert "2026-09-01" not in sql, "date value was formatted into SQL"


def test_injection_attempt_rejected(queries):
    with pytest.raises(ToolError, match="category must be one of"):
        call_tool(server.mcp, "get_waste_by_item", {"branch_id": 12, **RANGE, "category": "x' OR '1'='1"})
    assert queries == []


def test_hq_sees_any_branch(queries):
    result = call_tool(server.mcp, "get_daily_branch_sales", {"branch_id": 5, **RANGE})
    assert queries[0]["params"]["branch_id"] == 5
    assert "note" not in result


def test_manager_forced_to_own_branch(queries, monkeypatch):
    monkeypatch.setenv("LOCAL_ROLE", "manager")
    monkeypatch.setenv("LOCAL_BRANCH_ID", "12")
    result = call_tool(server.mcp, "get_daily_branch_sales", {"branch_id": 5, **RANGE})
    assert queries[0]["params"]["branch_id"] == 12
    assert "branch 12 instead of branch 5" in result["note"]


def test_manager_cannot_rank_branches(queries, monkeypatch):
    monkeypatch.setenv("LOCAL_ROLE", "manager")
    monkeypatch.setenv("LOCAL_BRANCH_ID", "12")
    with pytest.raises(ToolError, match="Only HQ"):
        call_tool(server.mcp, "get_top_branches", RANGE)


def test_user_without_branch_denied(queries, monkeypatch):
    monkeypatch.setenv("LOCAL_ROLE", "staff")
    with pytest.raises(ToolError, match="not linked to a branch"):
        call_tool(server.mcp, "get_waste_by_item", {"branch_id": 12, **RANGE})
