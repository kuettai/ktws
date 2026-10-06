#!/usr/bin/env python3
"""Render every Mermaid diagram in the workshops to SVG and PNG, and link them under the diagram.

For each ```mermaid block in a workshop page, this writes
    <page folder>/img/diagrams/<page>-<n>.svg   (vector: stays sharp at any zoom)
    <page folder>/img/diagrams/<page>-<n>.png   (2x bitmap)
and puts this line right under the block (added once, updated on later runs):
    Open full size: [PNG](img/diagrams/<page>-<n>.png) · [SVG](img/diagrams/<page>-<n>.svg)

Rendering uses headless Google Chrome and the Mermaid library, so the images match the site.
Re-run after editing a diagram:

    python3 render_diagrams.py                 # all workshops
    python3 render_diagrams.py AWS-001-AgenticFromScratch/day1/06-auth.md

Needs Google Chrome and Node.js (npm downloads Mermaid once into ~/.cache/ktws-mermaid).
"""
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSHOPS = ["AWS-001-AgenticFromScratch"]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
MERMAID_VERSION = "11"
CACHE = Path.home() / ".cache" / "ktws-mermaid"
SKIP_DIRS = {".venv", "node_modules", "cdk.out", "_site", "_site_src"}
SCALE = 2          # PNG pixel density
PAD = 24           # white margin around the diagram, in CSS pixels

BLOCK = re.compile(r"^( *)```mermaid\n(.*?)^\1```\n(?:\n?\1Open full size: .*\n)?", re.M | re.S)


def mermaid_js() -> Path:
    js = CACHE / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"
    if not js.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["npm", "install", "--prefix", str(CACHE), "--silent", f"mermaid@{MERMAID_VERSION}"], check=True)
    return js


def chrome(*args: str) -> str:
    out = subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", *args],
                         capture_output=True, text=True, timeout=120)
    return out.stdout


def render_svg(source: str, js: Path, workdir: Path) -> str:
    """Let Mermaid render the diagram in headless Chrome and return the SVG markup."""
    page = workdir / "render.html"
    page.write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<script src="{js.as_uri()}"></script></head><body><pre id="out"></pre>
<script>
mermaid.initialize({{ startOnLoad: false, theme: "default", securityLevel: "loose",
                      flowchart: {{ htmlLabels: false }}, fontFamily: "Helvetica, Arial, sans-serif" }});
mermaid.render("d", {json.dumps(source)})
  .then(r => {{ document.getElementById("out").textContent = r.svg; }})
  .catch(e => {{ document.getElementById("out").textContent = "ERROR " + e; }});
</script></body></html>""", encoding="utf-8")
    dom = chrome("--virtual-time-budget=10000", "--allow-file-access-from-files", "--dump-dom", page.as_uri())
    match = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    svg = html.unescape(match.group(1)) if match else ""
    if not svg.startswith("<svg"):
        raise RuntimeError(svg[:300] or "Chrome returned no SVG")
    return svg


def size_of(svg: str) -> tuple[float, float]:
    x, y, w, h = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split())
    return w, h


def standalone(svg: str) -> str:
    """Give the SVG a fixed size, a white background and a margin, so it opens nicely on its own."""
    w, h = size_of(svg)
    svg = re.sub(r'\sstyle="max-width:[^"]*"', "", svg, count=1)
    svg = re.sub(r'\swidth="[^"]*"', "", svg, count=1)
    x, y, vw, vh = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split())
    svg = svg.replace(f'viewBox="{re.search(r"viewBox=\"([^\"]+)\"", svg).group(1)}"',
                      f'viewBox="{x - PAD} {y - PAD} {vw + 2 * PAD} {vh + 2 * PAD}" '
                      f'width="{w + 2 * PAD:.0f}" height="{h + 2 * PAD:.0f}"', 1)
    return svg.replace(">", f'><rect x="{x - PAD}" y="{y - PAD}" width="{vw + 2 * PAD}" '
                            f'height="{vh + 2 * PAD}" fill="#ffffff"/>', 1)


def render_png(svg_file: Path, png_file: Path) -> None:
    w, h = size_of(svg_file.read_text(encoding="utf-8"))
    chrome(f"--force-device-scale-factor={SCALE}", f"--window-size={int(w) + 1},{int(h) + 1}",
           "--default-background-color=ffffffff", f"--screenshot={png_file}", svg_file.as_uri())
    if not png_file.exists() or png_file.stat().st_size == 0:
        raise RuntimeError(f"no PNG written for {svg_file.name}")


def pages(args: list[str]) -> list[Path]:
    if args:
        return [ROOT / a for a in args]
    found = []
    for ws in WORKSHOPS:
        for p in sorted((ROOT / ws).rglob("*.md")):
            if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts):
                found.append(p)
    return found


def main() -> None:
    js = mermaid_js()
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for page in pages(sys.argv[1:]):
            text = page.read_text(encoding="utf-8")
            if "```mermaid" not in text:
                continue
            out_dir = page.parent / "img" / "diagrams"
            out_dir.mkdir(parents=True, exist_ok=True)
            count = 0

            def replace(m: re.Match) -> str:
                nonlocal count
                count += 1
                indent, body = m.group(1), m.group(2)
                source = "\n".join(l[len(indent):] if l.startswith(indent) else l for l in body.rstrip("\n").split("\n"))
                name = f"{page.stem}-{count}"
                svg_file, png_file = out_dir / f"{name}.svg", out_dir / f"{name}.png"
                svg_file.write_text(standalone(render_svg(source, js, Path(tmp))), encoding="utf-8")
                render_png(svg_file, png_file)
                rel = os.path.relpath(out_dir, page.parent)
                link = f"{indent}Open full size: [PNG]({rel}/{name}.png) · [SVG]({rel}/{name}.svg)\n"
                return f"{indent}```mermaid\n{body}{indent}```\n\n{link}"

            new = BLOCK.sub(replace, text)
            if new != text:
                page.write_text(new, encoding="utf-8")
            print(f"{page.relative_to(ROOT)}: {count} diagram(s)")
            total += count
    print(f"Rendered {total} diagram(s) to SVG and PNG")


if __name__ == "__main__":
    main()
