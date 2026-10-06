#!/usr/bin/env python
"""Fix mermaid syntax errors inside GRAPHICAL_ABSTRACT.md (idempotent)."""
import re
from pathlib import Path

MD = Path(__file__).parent / "GRAPHICAL_ABSTRACT.md"


def fix_mermaid(text: str) -> str:
    text = re.sub(r"\[/([^\]/]+)\]", r"[/\1/]", text)

    def quote(m: re.Match) -> str:
        content = m.group(1)
        if content.startswith("(") and content.endswith(")"):
            return m.group(0)
        if content.startswith('"') and content.endswith('"'):
            return m.group(0)
        if "(" in content or ")" in content:
            return f'["{content}"]'
        return m.group(0)

    return re.sub(r"\[([^\[\]]+)\]", quote, text)


def main() -> None:
    content = MD.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        return "```mermaid\n" + fix_mermaid(m.group(1)) + "\n```"

    new_content = re.sub(r"```mermaid\n(.*?)\n```", repl, content, flags=re.DOTALL)

    if new_content == content:
        print("No changes needed")
    else:
        MD.write_text(new_content, encoding="utf-8")
        print(f"Updated {MD}")


if __name__ == "__main__":
    main()
