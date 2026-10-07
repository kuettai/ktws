#!/usr/bin/env python3
"""Call a remote MCP server from the terminal, with your sign-in token (Day 2).

    uv run --directory solutions/mcp-server python ../../scripts/mcp_call.py <url> list
    uv run --directory solutions/mcp-server python ../../scripts/mcp_call.py <url> call <tool> [name=value ...]

Examples:
    ... mcp_call.py "$GATEWAY_URL" list
    ... mcp_call.py "$GATEWAY_URL" call RstMcp___who_am_i
    ... mcp_call.py "$GATEWAY_URL" call OpsApi___getStockLevels branchId=12

The token comes from the RST_MCP_TOKEN environment variable (scripts/get_token.py prints one).
Arguments are name=value pairs, so no JSON quoting is needed on Windows. Each value is converted
to the type the tool's input schema asks for (number, true/false or text). A refused call (for
example by a Gateway policy) prints DENIED and the reason. It runs with the MCP SDK installed in
solutions/mcp-server, hence the `uv run --directory` in front.
"""
import asyncio
import json
import logging
import os
import sys

import httpx2
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError as McpError


def parse_args(pairs: list[str], schema: dict) -> dict:
    """name=value pairs -> arguments, typed as the tool's input schema says."""
    props = (schema or {}).get("properties", {})
    args = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"Arguments must be name=value, got {pair!r}")
        name, value = pair.split("=", 1)
        kind = props.get(name, {}).get("type")
        if kind == "integer":
            args[name] = int(value)
        elif kind == "number":
            args[name] = float(value)
        elif kind == "boolean":
            args[name] = value.lower() in ("true", "yes", "1")
        else:
            args[name] = value
    return args


async def all_tools(session: ClientSession) -> list:
    tools, cursor = [], None
    while True:  # the tool list comes in pages (Gateway: 30 per page)
        page = await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor) if cursor else None)
        tools += page.tools
        cursor = page.next_cursor
        if not cursor:
            return tools


async def main() -> None:
    logging.basicConfig(level=logging.ERROR)  # hide SDK warnings about tools it has not listed
    if len(sys.argv) < 3 or sys.argv[2] not in ("list", "call") or (sys.argv[2] == "call" and len(sys.argv) < 4):
        sys.exit(__doc__)
    url, command = sys.argv[1], sys.argv[2]
    token = os.environ.get("RST_MCP_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(headers=headers, timeout=60) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, *_):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name: t for t in await all_tools(session)}
                if command == "list":
                    print(f"{len(tools)} tools:")
                    for name in sorted(tools):
                        print(f"  {name}")
                    return
                name = sys.argv[3]
                if name not in tools:
                    print(f"Note: {name} is not in your tool list (a Gateway policy may hide it from you). Calling it anyway.")
                schema = tools[name].input_schema if name in tools else {}
                try:
                    result = await session.call_tool(name, parse_args(sys.argv[4:], schema))
                except McpError as e:
                    print(f"DENIED\n{e}")
                    return
                print("ERROR" if getattr(result, "is_error", False) else "OK")
                for item in getattr(result, "content", []):
                    text = getattr(item, "text", None)
                    try:
                        print(json.dumps(json.loads(text), indent=2) if text else item)
                    except (TypeError, ValueError):
                        print(text)


if __name__ == "__main__":
    asyncio.run(main())
