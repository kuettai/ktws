"""Creates the shared MCP server instance. Tool modules import `mcp` from here."""
import logging
import os

from mcp.server.mcpserver import MCPServer

from lib.auth import build_auth

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

auth_settings, token_verifier = build_auth()

mcp = MCPServer(
    "rst",
    instructions=(
        "Tools for a quick-service restaurant chain. Money is in USD. Dates are YYYY-MM-DD. "
        "Use Redshift tools (get_*_sales, get_top_*, get_waste_*) for history up to yesterday, "
        "and operations tools (get_current_stock, get_today_sales, list_orders_today) for live data. "
        "When the user says 'my branch' or 'my store', call who_am_i to get their branch_id. "
        "If you only know a branch name, call find_branch first."
    ),
    auth=auth_settings,
    token_verifier=token_verifier,
)
