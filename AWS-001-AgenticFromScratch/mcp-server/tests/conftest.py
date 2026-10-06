import asyncio
import json
import os

for var in ("OIDC_ISSUER", "LOCAL_ROLE", "LOCAL_BRANCH_ID"):
    os.environ.pop(var, None)
os.environ.setdefault("REDSHIFT_DATABASE", "dev")
os.environ.setdefault("REDSHIFT_WORKGROUP", "test")


def call_tool(mcp, name: str, args: dict):
    """Call a tool in-process and return its structured result."""
    result = asyncio.run(mcp.call_tool(name, args))
    # dict returns are sent as JSON text; typed returns (str, list, models) as structured content
    return result.structured_content or json.loads(result.content[0].text)
