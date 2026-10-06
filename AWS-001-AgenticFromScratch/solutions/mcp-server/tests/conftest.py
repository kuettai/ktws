import asyncio
import json
import os

import pytest

for var in ("OIDC_ISSUER", "LOCAL_ROLE", "LOCAL_BRANCH_ID"):
    os.environ.pop(var, None)
os.environ.setdefault("REDSHIFT_DATABASE", "dev")
os.environ.setdefault("REDSHIFT_WORKGROUP", "test")


def call_tool(mcp, name: str, args: dict):
    """Call a tool in-process and return its structured result."""
    result = asyncio.run(mcp.call_tool(name, args))
    # dict returns are sent as JSON text; typed returns (str, list, models) as structured content
    return result.structured_content or json.loads(result.content[0].text)


@pytest.fixture
def queries(monkeypatch):
    """Capture SQL sent to Redshift instead of running it."""
    import tools.redshift_tools as rt

    captured = []

    def fake_run_query(sql, params=None):
        captured.append({"sql": sql, "params": params})
        return [{"ok": 1}]

    monkeypatch.setattr(rt, "run_query", fake_run_query)
    return captured
