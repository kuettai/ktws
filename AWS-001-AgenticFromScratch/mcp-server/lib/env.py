"""Load settings from a .env file for local runs (MCP Inspector, Kiro, plain `uv run`).

Lines look like KEY=value. Blank lines and lines starting with # are skipped, and quotes around
a value are removed. Variables already set in the environment win, so a value exported in your
shell or set in Kiro's mcp.json "env" block overrides .env. In a container there is no .env
file and nothing happens. Works the same on Windows, macOS and Linux.
"""
import os
from pathlib import Path


def load_env_file(path: Path) -> list[str]:
    """Set variables from `path` that are not set yet. Returns the names it set."""
    if not path.is_file():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip().removeprefix("export ").strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
