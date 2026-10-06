"""The data dictionary must match the real views, and the server's copy must match docs/.

Kiro writes SQL from the dictionary (kiro/steering/sql-rules.md includes it), so a stale
dictionary means SQL against columns that don't exist.
"""
import asyncio
import re
from pathlib import Path

HERE = Path(__file__).resolve()
WORKSHOP = next(p for p in HERE.parents if (p / "docs" / "data-dictionary.md").exists())
SERVER = HERE.parents[1]


def dictionary_columns(text: str) -> dict[str, list[str]]:
    """{"mcp.v_x": [columns...]} from the '### `mcp.v_x`' sections and their tables."""
    views, current = {}, None
    for line in text.splitlines():
        heading = re.match(r"^###\s+`(mcp\.v_[a-z_]+)`", line)
        if heading:
            current = heading.group(1); views[current] = []
        elif current and (cell := re.match(r"^\|\s*`([a-z_]+)`\s*\|", line)):
            views[current].append(cell.group(1))
    return views


def split_top_level(select_list: str) -> list[str]:
    parts, depth, buf = [], 0, ""
    for ch in select_list:
        depth += ch == "("; depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(buf); buf = ""
        else:
            buf += ch
    return parts + [buf]


def top_level_select(body: str) -> str:
    """The column list between SELECT and the FROM that is not inside brackets
    (EXTRACT(HOUR FROM ...) has a FROM of its own)."""
    start = re.search(r"\bSELECT\s", body, re.I).end()
    depth = 0
    for i in range(start, len(body)):
        depth += body[i] == "("; depth -= body[i] == ")"
        if depth == 0 and re.match(r"\sFROM\s", body[i:i + 6], re.I):
            return body[start:i]
    raise ValueError("no FROM found")


def sql_columns(text: str) -> dict[str, list[str]]:
    """{"mcp.v_x": [output columns...]} from CREATE VIEW ... AS SELECT <list> FROM ..."""
    views = {}
    for name, body in re.findall(r"CREATE OR REPLACE VIEW (mcp\.v_[a-z_]+) AS\s+(.*?);", text, re.S | re.I):
        select = top_level_select(body)
        cols = []
        for expr in split_top_level(select):
            expr = " ".join(expr.split())
            alias = re.search(r"\bAS\s+([a-z_]+)\s*$", expr, re.I)
            cols.append(alias.group(1) if alias else expr.split(".")[-1])
        views[name] = cols
    return views


def test_server_copy_matches_docs():
    assert (SERVER / "context" / "data-dictionary.md").read_text() == \
        (WORKSHOP / "docs" / "data-dictionary.md").read_text(), \
        "copy docs/data-dictionary.md to mcp-server/context/ (the server ships its own copy)"


def test_dictionary_matches_views_sql():
    documented = dictionary_columns((WORKSHOP / "docs" / "data-dictionary.md").read_text())
    real = sql_columns((WORKSHOP / "data" / "views.sql").read_text())
    assert sorted(documented) == sorted(real), "views listed in the dictionary differ from data/views.sql"
    for view, cols in real.items():
        assert documented[view] == cols, f"{view}: dictionary {documented[view]} vs views.sql {cols}"


def test_dictionary_is_an_mcp_resource():
    import tools.context  # noqa: F401  registers the resource
    from app import mcp

    listed = asyncio.run(mcp.list_resources())
    assert "rst://data-dictionary" in [str(r.uri) for r in listed]
    contents = list(asyncio.run(mcp.read_resource("rst://data-dictionary")))
    assert "mcp.v_daily_branch_sales" in contents[0].content
