"""Connect the agent to the restaurant MCP server.

Local (stdio): the agent starts the MCP server as a child process, as Kiro does.
    The caller identity comes from LOCAL_ROLE / LOCAL_BRANCH_ID (no sign-in).
Remote (Streamable HTTP): ECS, AgentCore Runtime or AgentCore Gateway, with a bearer token.
    The caller identity comes from the token.

Environment:
    MCP_URL         remote endpoint, e.g. https://xxxx.cloudfront.net/mcp. Unset = local stdio.
    MCP_TOKEN       bearer token for MCP_URL (scripts/get_token.py prints one)
    MCP_SERVER_DIR  local server folder, default solutions/mcp-server
"""
import os
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient

DEFAULT_SERVER_DIR = Path(__file__).resolve().parents[3] / "mcp-server"  # solutions/mcp-server


def stdio_server(
    server_dir: str | Path | None = None,
    *,
    role: str | None = None,
    branch_id: int | None = None,
    env: dict[str, str] | None = None,
) -> MCPClient:
    """Start the MCP server locally with `uv run python server.py`.

    role / branch_id simulate a signed-in user: "hq", or "manager"/"staff" with a branch.
    """
    server_dir = Path(server_dir or os.environ.get("MCP_SERVER_DIR") or DEFAULT_SERVER_DIR)
    child_env = {**os.environ, **(env or {}), "MCP_TRANSPORT": "stdio"}
    if role:
        child_env["LOCAL_ROLE"] = role
    if branch_id is not None:
        child_env["LOCAL_BRANCH_ID"] = str(branch_id)
    elif role:
        child_env.pop("LOCAL_BRANCH_ID", None)
    params = StdioServerParameters(
        command="uv", args=["run", "--quiet", "python", "server.py"], cwd=str(server_dir), env=child_env
    )
    return MCPClient(lambda: stdio_client(params))


def http_server(url: str | None = None, token: str | None = None) -> MCPClient:
    """Connect to a remote MCP endpoint over Streamable HTTP."""
    url = url or os.environ.get("MCP_URL")
    if not url:
        raise ValueError("Set MCP_URL or pass url")
    token = token or os.environ.get("MCP_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return MCPClient(url=url, headers=headers)


def server_from_env(*, role: str | None = None, branch_id: int | None = None) -> MCPClient:
    """Remote if MCP_URL is set, otherwise local stdio."""
    if os.environ.get("MCP_URL"):
        return http_server()
    return stdio_server(role=role, branch_id=branch_id)
