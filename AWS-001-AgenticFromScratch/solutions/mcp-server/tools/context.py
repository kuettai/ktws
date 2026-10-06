"""MCP resources: read-only context a client can load, as opposed to tools the model calls.

The data dictionary is a copy of docs/data-dictionary.md shipped with the server (the container
image only contains this folder). tests/test_data_dictionary.py fails if the copy goes stale.
"""
from pathlib import Path

from app import mcp

DICTIONARY = Path(__file__).resolve().parents[1] / "context" / "data-dictionary.md"


@mcp.resource(
    "rst://data-dictionary",
    name="data_dictionary",
    title="Data dictionary",
    description="The curated mcp views: every view, column, type and meaning. Read this to know "
                "which data exists before choosing a tool.",
    mime_type="text/markdown",
)
def data_dictionary() -> str:
    return DICTIONARY.read_text(encoding="utf-8")
