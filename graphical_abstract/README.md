# Graphical Abstract

Single poster-style image summarizing the Subdomain Finder Bot project:
title banner → request pipeline → system architecture diagram → key features.

## Files

| File | Description |
|------|-------------|
| `graphical_abstract.png` | High-resolution poster (3672×3719, lossless) |
| `graphical_abstract.jpg` | Web-friendly version (quality 93) |
| `build_abstract.py` | Script that generates the poster |

## Rebuild

```bash
# mermaid.min.js must exist in the project root (gitignored):
#   Invoke-WebRequest "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js" -OutFile mermaid.min.js
venv\Scripts\python.exe graphical_abstract\build_abstract.py
```

Requires Microsoft Edge (used headless for rendering) and Pillow.
The architecture diagram is extracted from `GRAPHICAL_ABSTRACT.md`
(first mermaid block, syntax-fixed via `fix_md.fix_mermaid`).
