#!/usr/bin/env python3
"""Prepare the website sources for MkDocs.

Each workshop lives in its own folder ({CATEGORY}-{###}-{TITLE}) with its guides next to its code,
so the repo reads well on GitHub. MkDocs needs all pages under one folder, so this script copies
them to _site_src/ and:

  - every README.md becomes index.md: the repo README is the site home page, a workshop README
    its overview page
  - links to code (../mcp-server/server.py, ../infra/) point at the file on GitHub
  - "> **Preview** - ..." notes become a styled warning box
  - "> **Screenshot** - ..." placeholders become a "Screenshot to prepare" box
    (grep SCREENSHOT_YET_TO_PREPARE to list what is still missing)
  - <details> blocks (quiz answers) get their markdown rendered
  - a ```bash block followed by a ```powershell block becomes "macOS / Linux" | "Windows" tabs
  - fails on markdown that would render wrongly (list or code block glued to a paragraph)
  - images under img/ folders (diagram PNG/SVG from render_diagrams.py, screenshots) are copied

    python3 build_site.py && mkdocs serve          # preview on http://127.0.0.1:8000/ktws/
    python3 build_site.py && mkdocs build --strict

To add a workshop: create its folder, add it to WORKSHOPS, and add its pages to the nav in mkdocs.yml.
"""
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site_src"
REPO_URL = os.environ.get("REPO_URL", "https://github.com/kuettai/ktws")
BRANCH = os.environ.get("REPO_BRANCH", "main")
WORKSHOPS = ["AWS-001-AgenticFromScratch"]
SKIP_DIRS = {".venv", "node_modules", "cdk.out", ".pytest_cache", "__pycache__", "_site", "_site_src"}

LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")
PREVIEW = re.compile(r"^> \*\*Preview\*\*\s*[—-]\s*(.+)$", re.MULTILINE)
# "> **Screenshot** — `<SCREENSHOT_YET_TO_PREPARE>` what to capture · save as `img/x.png`"
SCREENSHOT = re.compile(r"^( *)> \*\*Screenshot\*\*\s*[—-]\s*(.+)$", re.MULTILINE)
# A ```bash block followed (one blank line) by a ```powershell block, at the same indent.
SHELL_PAIR = re.compile(r"^( *)```bash\n(.*?)^\1```\n\n\1```powershell\n(.*?)^\1```\n", re.M | re.S)


def shell_tabs(m: re.Match) -> str:
    """Turn a bash + PowerShell pair into "macOS / Linux" and "Windows (PowerShell)" tabs."""
    ind, bash, ps = m.group(1), m.group(2), m.group(3)

    def block(lang: str, body: str) -> str:
        lines = [f"{ind}    ```{lang}"] + [("    " + l) if l.strip() else l for l in body.rstrip("\n").split("\n")]
        return "\n".join(lines) + f"\n{ind}    ```\n"

    return (f'{ind}=== "macOS / Linux"\n\n{block("bash", bash)}\n'
            f'{ind}=== "Windows (PowerShell)"\n\n{block("powershell", ps)}')


def workshop_pages(ws: str) -> list[str]:
    """Every markdown file in a workshop folder, relative to the repo root."""
    pages = []
    for path in sorted((ROOT / ws).rglob("*.md")):
        if not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            pages.append(str(path.relative_to(ROOT)))
    return pages


PAGES = ["README.md"] + [p for ws in WORKSHOPS for p in workshop_pages(ws)]
IMAGE_TYPES = {".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp"}
# Images under any img/ folder are published with the site (diagrams, screenshots).
IMAGES = sorted(str(p.relative_to(ROOT)) for ws in WORKSHOPS for p in (ROOT / ws).rglob("*")
                if p.suffix.lower() in IMAGE_TYPES and "img" in p.relative_to(ROOT).parts
                and not SKIP_DIRS.intersection(p.relative_to(ROOT).parts))


def site_path(page: str) -> str:
    """README.md pages become index.md, so they are the landing page of their folder."""
    head, name = os.path.split(page)
    return os.path.join(head, "index.md") if name == "README.md" else page


def rewrite_link(target: str, page: str) -> str:
    if re.match(r"^[a-z]+:", target) or target.startswith("#"):
        return target
    path, _, anchor = target.partition("#")
    resolved = os.path.normpath(os.path.join(os.path.dirname(page), path))
    suffix = "#" + anchor if anchor else ""
    if resolved in PAGES:
        return os.path.relpath(site_path(resolved), os.path.dirname(site_path(page)) or ".") + suffix
    if resolved in IMAGES:
        return os.path.relpath(resolved, os.path.dirname(site_path(page)) or ".") + suffix
    kind = "tree" if (ROOT / resolved).is_dir() else "blob"
    return f"{REPO_URL}/{kind}/{BRANCH}/{resolved}" + suffix


LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+\.)\s+")


def lint(page: str, text: str) -> list[str]:
    """Markdown that GitHub renders but MkDocs merges into the paragraph above: a list item or a
    code fence straight after paragraph text, with no blank line in between."""
    problems, fence, prev = [], False, ""
    for n, line in enumerate(text.split("\n"), 1):
        stripped = line.lstrip()
        opens_fence = stripped.startswith("```") and not fence
        if not fence and (LIST_ITEM.match(line) or opens_fence) and prev.strip():
            p = prev.lstrip()
            if not LIST_ITEM.match(prev) and not p.startswith(("|", "#", ">", "<", "```", "!!!")):
                problems.append(f"{page}:{n}: add a blank line before this line")
        if stripped.startswith("```"):
            fence = not fence
        prev = line
    return problems


def main() -> None:
    problems = [p for page in PAGES for p in lint(page, (ROOT / page).read_text(encoding="utf-8"))]
    if problems:
        raise SystemExit("Markdown formatting problems (they render wrongly on the site):\n  "
                         + "\n  ".join(problems))
    shutil.rmtree(OUT, ignore_errors=True)
    for page in PAGES:
        text = (ROOT / page).read_text(encoding="utf-8")
        text = LINK.sub(lambda m: m.group(1) + rewrite_link(m.group(2), page) + m.group(3), text)
        text = PREVIEW.sub(lambda m: f'!!! warning "Preview"\n    {m.group(1)}', text)
        text = SHELL_PAIR.sub(shell_tabs, text)
        text = SCREENSHOT.sub(lambda m: f'{m.group(1)}!!! example "Screenshot to prepare"\n{m.group(1)}    {m.group(2)}', text)
        # GitHub renders markdown inside <details>; MkDocs (md_in_html) only when asked to.
        text = text.replace("<details>", '<details markdown="1">')
        dest = OUT / site_path(page)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    for image in IMAGES:
        (OUT / image).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / image, OUT / image)
    shutil.copytree(ROOT / "site-assets", OUT / "assets", dirs_exist_ok=True)  # site JS/CSS
    print(f"Wrote {len(PAGES)} pages and {len(IMAGES)} images to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
