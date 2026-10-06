"""restaurant MCP server entry point.

    MCP_TRANSPORT=stdio  (default)  local, launched by Kiro or MCP Inspector
    MCP_TRANSPORT=http              Streamable HTTP on 0.0.0.0:$PORT/mcp, for containers
"""
import os
from pathlib import Path

from lib.env import load_env_file

# Read .env next to this file before anything else reads settings (local runs only).
load_env_file(Path(__file__).resolve().parent / ".env")

from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse

from app import mcp  # noqa: E402
import tools.hello  # noqa: F401  (importing registers the tools)
import tools.context  # noqa: F401  (MCP resource: the data dictionary)
import tools.ops_tools  # noqa: F401
import tools.promo_tools  # noqa: F401
import tools.redshift_tools  # noqa: F401
import tools.write_tools  # noqa: F401


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def main() -> None:
    if os.environ.get("MCP_TRANSPORT", "stdio") == "stdio":
        mcp.run()
        return
    # Stateless + JSON responses: any task behind the load balancer can serve any request,
    # and no long-lived SSE streams through ALB / CloudFront.
    mcp.run(
        "streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
