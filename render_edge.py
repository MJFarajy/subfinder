#!/usr/bin/env python
"""Render Mermaid diagrams to PNG/JPG using Edge headless + Pillow."""

import re
import subprocess
import sys
from pathlib import Path
from html import escape
from PIL import Image, ImageChops

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = Path(__file__).parent
OUT = ROOT / "diagrams"
WORK = ROOT / "_render_tmp"
MERMAID_JS = ROOT / "mermaid.min.js"

# Diagram titles in order of appearance in GRAPHICAL_ABSTRACT.md
TITLES = [
    "01_system_architecture",
    "02_request_flow_sequence",
    "03_key_components_detail",
    "04_deployment_topology",
    "05_design_principles_mindmap",
]

# Screenshot window sizes (logical px, scale=2 -> actual pixels doubled)
SIZES = [
    (1800, 2200),
    (1600, 1600),
    (1600, 4500),
    (1400, 900),
    (1400, 1000),
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 30px; background: #ffffff; }}
  .mermaid {{ display: flex; justify-content: center; }}
</style>
</head>
<body>
<pre class="mermaid">{diagram}</pre>
<script src="file:///{js_path}"></script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});
</script>
</body>
</html>
"""


def fix_mermaid(text: str) -> str:
    """Fix mermaid 10 parse errors: unquoted parens in labels, bad parallelograms."""
    # 1. Malformed parallelogram shape [/text] -> [/text/]
    text = re.sub(r"\[/([^\]/]+)\]", r"[/\1/]", text)
    # 2. Quote square-bracket labels containing parentheses
    def quote(m: re.Match) -> str:
        content = m.group(1)
        if content.startswith("(") and content.endswith(")"):
            return m.group(0)  # cylinder shape [(...)] - keep as-is
        if content.startswith('"') and content.endswith('"'):
            return m.group(0)  # already quoted
        if "(" in content or ")" in content:
            return f'["{content}"]'
        return m.group(0)
    return re.sub(r"\[([^\[\]]+)\]", quote, text)


def extract_diagrams(md_path: Path) -> list:
    content = md_path.read_text(encoding="utf-8")
    blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
    return [fix_mermaid(b) for b in blocks]


def screenshot(html_path: Path, png_path: Path, w: int, h: int) -> None:
    cmd = [
        EDGE,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        "--no-first-run",
        "--user-data-dir=" + str(WORK / "profile"),
        "--force-device-scale-factor=2",
        "--virtual-time-budget=15000",
        f"--window-size={w},{h}",
        "--screenshot=" + str(png_path),
        html_path.as_uri(),
    ]
    subprocess.run(cmd, capture_output=True, timeout=90, check=True)


def trim_and_save(png_path: Path, base_path: Path) -> None:
    img = Image.open(png_path).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        pad = 20
        left = max(bbox[0] - pad, 0)
        top = max(bbox[1] - pad, 0)
        right = min(bbox[2] + pad, img.width)
        bottom = min(bbox[3] + pad, img.height)
        img = img.crop((left, top, right, bottom))
    img.save(base_path.with_suffix(".png"))
    img.save(base_path.with_suffix(".jpg"), quality=92)
    print(f"  PNG: {base_path.with_suffix('.png').name} ({img.width}x{img.height})")
    print(f"  JPG: {base_path.with_suffix('.jpg').name} ({base_path.with_suffix('.jpg').stat().st_size:,} bytes)")


def main() -> None:
    if not Path(EDGE).exists():
        sys.exit(f"Edge not found: {EDGE}")
    if not MERMAID_JS.exists():
        sys.exit("mermaid.min.js not found - download it first")

    diagrams = extract_diagrams(ROOT / "GRAPHICAL_ABSTRACT.md")
    print(f"Found {len(diagrams)} diagrams\n")

    OUT.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)

    ok = 0
    for i, diagram in enumerate(diagrams):
        title = TITLES[i] if i < len(TITLES) else f"diagram_{i+1}"
        w, h = SIZES[i] if i < len(SIZES) else (1600, 1500)
        print(f"[{i+1}/{len(diagrams)}] {title}")

        html_path = WORK / f"{title}.html"
        html_path.write_text(
            HTML_TEMPLATE.format(diagram=diagram.strip(), js_path=str(MERMAID_JS).replace("\\", "/")),
            encoding="utf-8",
        )

        raw_png = WORK / f"{title}_raw.png"
        try:
            screenshot(html_path, raw_png, w, h)
            if not raw_png.exists() or raw_png.stat().st_size == 0:
                print("  FAIL: no screenshot produced")
                continue
            trim_and_save(raw_png, OUT / title)
            ok += 1
        except Exception as e:
            print(f"  FAIL: {e}")

    print(f"\nDone: {ok}/{len(diagrams)} diagrams -> {OUT}")


if __name__ == "__main__":
    main()
