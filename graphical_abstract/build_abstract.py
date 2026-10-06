#!/usr/bin/env python
"""Build a single poster-style graphical abstract image for the project.

Output:
    graphical_abstract/graphical_abstract.png  (high-res)
    graphical_abstract/graphical_abstract.jpg  (web-friendly)

Pipeline: HTML poster (title + pipeline + architecture diagram + feature chips)
          -> Edge headless screenshot -> Pillow trim -> PNG + JPG
"""

import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from fix_md import fix_mermaid  # noqa: E402

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
MERMAID_JS = ROOT / "mermaid.min.js"
SOURCE_MD = ROOT / "GRAPHICAL_ABSTRACT.md"

OUT_PNG = HERE / "graphical_abstract.png"
OUT_JPG = HERE / "graphical_abstract.jpg"
SHOT = HERE / "_shot.png"
PAGE = HERE / "_page.html"

# Render window (logical px); screenshot scaled 2x for high resolution
WINDOW_W = 1900
WINDOW_H = 2500
SCALE = 2

PIPELINE_STEPS = [
    ("👤", "User", "Bale / Telegram"),
    ("🔍", "Normalize", "strip URL, www, port, path"),
    ("💾", "Cache L1+L2", "memory + SQLite, TTL 600s"),
    ("⏱️", "Rate Limit", "60 req/min + FIFO queue"),
    ("🌐", "AgniOps API", "GET /v1/search?domain="),
    ("📤", "Results", "sorted, deduped → .txt"),
]

FEATURES = [
    "Dual Platform (Bale + Telegram)",
    "Fully Async (httpx / aiogram)",
    "Persistent Cache survives restarts",
    "Sliding-Window Rate Limiting",
    "429 Retry with Backoff",
    "Bilingual EN / فارسی",
    "Queue Position Updates",
    "Docker Ready + Auto-Restart",
]

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: {width}px;
    font-family: "Segoe UI", Arial, sans-serif;
    background: #ffffff;
    padding: 44px;
    color: #1a2333;
  }}
  .header {{
    background: linear-gradient(135deg, #0d2b4e 0%, #14538e 100%);
    color: #fff;
    border-radius: 16px;
    padding: 30px 40px;
    text-align: center;
  }}
  .header h1 {{ font-size: 46px; font-weight: 700; letter-spacing: 0.5px; }}
  .header p {{ font-size: 21px; margin-top: 10px; color: #bcd8f5; }}
  .section-label {{
    font-size: 24px; font-weight: 700; color: #14538e;
    margin: 34px 0 16px 4px; text-transform: uppercase; letter-spacing: 1.5px;
  }}
  .pipeline {{
    display: flex; align-items: stretch; justify-content: space-between; gap: 6px;
  }}
  .step {{
    flex: 1;
    background: #eef5fd;
    border: 2px solid #14538e;
    border-radius: 12px;
    padding: 14px 10px;
    text-align: center;
  }}
  .step .ico {{ font-size: 30px; }}
  .step .name {{ font-size: 19px; font-weight: 700; margin-top: 6px; color: #0d2b4e; }}
  .step .desc {{ font-size: 14.5px; color: #3d5a80; margin-top: 5px; line-height: 1.3; }}
  .arrow {{ align-self: center; font-size: 30px; color: #14538e; font-weight: 700; }}
  .arch {{
    border: 2px solid #d4e3f5;
    border-radius: 16px;
    padding: 18px;
    background: #fbfdff;
    overflow: hidden;
  }}
  .mermaid {{ display: flex; justify-content: center; }}
  .chips {{
    display: flex; flex-wrap: wrap; justify-content: center; gap: 12px;
    margin-top: 6px;
  }}
  .chip {{
    background: #fff4e0;
    border: 1.5px solid #ef8f1f;
    color: #8a4b00;
    border-radius: 999px;
    padding: 9px 20px;
    font-size: 17.5px;
    font-weight: 600;
  }}
  .footer {{
    margin-top: 30px;
    text-align: center;
    font-size: 16.5px;
    color: #6b7f99;
    border-top: 2px solid #e3ebf5;
    padding-top: 16px;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>Subdomain Finder Bot &#8212; Graphical Abstract</h1>
    <p>Async dual-platform subdomain discovery with persistent caching, rate limiting &amp; bilingual UX</p>
  </div>

  <div class="section-label">Request Pipeline</div>
  <div class="pipeline">
{pipeline}
  </div>

  <div class="section-label">System Architecture</div>
  <div class="arch">
    <pre class="mermaid">{diagram}</pre>
  </div>

  <div class="section-label" style="text-align:center;">Key Features</div>
  <div class="chips">
{chips}
  </div>

  <div class="footer">
    github.com/MJFarajy/subfinder &nbsp;•&nbsp; Python 3.11+ / asyncio / httpx / SQLite &nbsp;•&nbsp; MIT License
  </div>

  <script src="file:///{js}"></script>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose',
      flowchart: {{ useMaxWidth: true, htmlLabels: true }} }});
  </script>
</body>
</html>
"""


def build_pipeline_html() -> str:
    parts = []
    for i, (ico, name, desc) in enumerate(PIPELINE_STEPS):
        if i:
            parts.append('    <div class="arrow">&#8594;</div>')
        parts.append(
            f'    <div class="step"><div class="ico">{ico}</div>'
            f'<div class="name">{name}</div><div class="desc">{desc}</div></div>'
        )
    return "\n".join(parts)


def build_chips_html() -> str:
    return "\n".join(f'    <div class="chip">{f}</div>' for f in FEATURES)


def extract_arch_diagram() -> str:
    content = SOURCE_MD.read_text(encoding="utf-8")
    blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
    if not blocks:
        raise SystemExit("No mermaid diagram found in GRAPHICAL_ABSTRACT.md")
    return fix_mermaid(blocks[0]).strip()  # system architecture diagram


def screenshot() -> None:
    cmd = [
        EDGE,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        "--no-first-run",
        "--user-data-dir=" + str(HERE / "_profile"),
        f"--force-device-scale-factor={SCALE}",
        "--virtual-time-budget=15000",
        f"--window-size={WINDOW_W},{WINDOW_H}",
        "--screenshot=" + str(SHOT),
        PAGE.as_uri(),
    ]
    subprocess.run(cmd, capture_output=True, timeout=120, check=True)


def trim_and_save() -> None:
    img = Image.open(SHOT).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bbox = ImageChops.difference(img, bg).getbbox()
    if not bbox:
        raise SystemExit("Screenshot is blank")
    pad = 24
    left, top = max(bbox[0] - pad, 0), max(bbox[1] - pad, 0)
    right = min(bbox[2] + pad, img.width)
    bottom = min(bbox[3] + pad, img.height)
    img = img.crop((left, top, right, bottom))
    img.save(OUT_PNG)
    img.save(OUT_JPG, quality=93)
    print(f"PNG: {OUT_PNG} ({img.width}x{img.height}, {OUT_PNG.stat().st_size:,} bytes)")
    print(f"JPG: {OUT_JPG} ({OUT_JPG.stat().st_size:,} bytes)")


def main() -> None:
    if not Path(EDGE).exists():
        raise SystemExit(f"Edge not found: {EDGE}")
    if not MERMAID_JS.exists():
        raise SystemExit("mermaid.min.js missing - download it first")

    html = HTML.format(
        width=WINDOW_W,
        pipeline=build_pipeline_html(),
        chips=build_chips_html(),
        diagram=extract_arch_diagram(),
        js=str(MERMAID_JS).replace("\\", "/"),
    )
    PAGE.write_text(html, encoding="utf-8")

    print("Rendering with Edge headless...")
    screenshot()
    if not SHOT.exists() or SHOT.stat().st_size == 0:
        raise SystemExit("No screenshot produced")

    trim_and_save()

    # Clean up temp artifacts
    for p in (PAGE, SHOT):
        p.unlink(missing_ok=True)
    profile = HERE / "_profile"
    if profile.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(profile)],
                       capture_output=True)

    print("Done.")


if __name__ == "__main__":
    main()
