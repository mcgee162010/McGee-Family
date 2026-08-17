#!/usr/bin/env python3
"""
Catch CSS/markup bugs in the generated family tree before they ship.

These are the checks that would have caught the "inline span" bug: every
element used as a block (avatar, name, relation, year) must be explicitly
declared display:block or the browser lays it out inline and the card collapses
into a run-on line of text.

Usage:  python3 scripts/test_render.py
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "levi-family-tree.html"

VOID = {"br", "img", "meta", "link", "input", "hr", "source", "area",
        "base", "col", "embed", "param", "track", "wbr"}


class Balance(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: stray </{tag}>")
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            open_tag, line = self.stack[-1]
            self.errors.append(
                f"line {self.getpos()[0]}: </{tag}> closes <{open_tag}> "
                f"opened on line {line}")


def css_block(css: str, selector: str) -> str:
    """Return the declarations for a selector (first exact match)."""
    pat = re.compile(
        r"(?:^|\}|\n)\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", re.S)
    m = pat.search(css)
    return m.group(1) if m else ""


def main() -> None:
    if not HTML.exists():
        sys.exit(f"{HTML.name} not found — run build_family_tree.py first")

    html = HTML.read_text(encoding="utf-8")
    css = "\n".join(re.findall(r"<style>(.*?)</style>", html, re.S))
    fails: list[str] = []
    checks = 0

    print("\n\033[1mRender checks\033[0m\n")

    # ── 1. markup balance ──────────────────────────────────────────
    b = Balance()
    b.feed(html)
    checks += 1
    if b.stack:
        fails.append(f"unclosed tags: {b.stack[:4]}")
    if b.errors:
        fails.append("mismatched tags: " + "; ".join(b.errors[:3]))

    # ── 2. spans used as blocks MUST declare display ──────────────
    # This is the check that would have caught the collapsed-card bug.
    block_spans = {
        ".av": "avatar wrapper (needs width/height to reserve space)",
        ".av-in": "avatar circle",
        ".nm": "person name (must sit on its own line)",
        ".rl": "relationship label (must sit on its own line)",
        ".lf": "life dates (must sit on its own line)",
        ".pip": "living/deceased dot",
        ".badge": "coming-soon badge",
    }
    for sel, why in block_spans.items():
        checks += 1
        decls = css_block(css, sel)
        if not decls:
            fails.append(f"{sel} has no CSS rule at all — {why}")
            continue
        if "display:" not in decls.replace(" ", ""):
            fails.append(
                f"{sel} is a <span> used as a block but never sets display "
                f"— browsers lay it out inline and the card collapses ({why})")

    # ── 3. the card must be a column ──────────────────────────────
    checks += 1
    card = css_block(css, ".p").replace(" ", "")
    if "display:flex" not in card or "flex-direction:column" not in card:
        fails.append(".p must be display:flex + flex-direction:column so the "
                     "avatar, name, relation and dates stack vertically")

    # ── 4. sized elements must not be inline ──────────────────────
    for sel in (".av", ".av-in", ".pip"):
        checks += 1
        decls = css_block(css, sel).replace(" ", "")
        if "width:" in decls and "display:inline;" in decls:
            fails.append(f"{sel} sets width but is display:inline — width is "
                         f"ignored on inline elements")

    # ── 5. every card has the parts we expect ─────────────────────
    cards = re.findall(r'<button class="p[^"]*"[^>]*>(.*?)</button>', html, re.S)
    checks += 1
    if not cards:
        fails.append("no person cards rendered")
    else:
        for i, c in enumerate(cards):
            missing = [k for k in ('class="av"', 'class="nm"', 'class="rl"')
                       if k not in c]
            if missing:
                fails.append(f"card {i} missing {missing}")
                break

    # ── 6. no leftover canvas machinery ──────────────────────────
    checks += 1
    for ghost in ("<svg", "pointerdown", "translate(", "__FAMILY__"):
        if ghost in html:
            fails.append(f"leftover canvas code found: {ghost!r}")
            break

    # ── 7. photos referenced actually exist and are lowercase ────
    checks += 1
    for src in set(re.findall(r'<img src="(photos/[^"]+)"', html)):
        if not (ROOT / src).is_file():
            fails.append(f"missing photo: {src}")
        elif src != src.lower():
            fails.append(f"photo path not lowercase (breaks on Pages): {src}")

    # ── 8. accessibility basics ──────────────────────────────────
    checks += 1
    if len(re.findall(r'<button class="p[^"]*"(?![^>]*aria-label)', html)):
        fails.append("some person cards lack aria-label")
    if 'lang="en"' not in html:
        fails.append("missing lang attribute")

    # ── report ───────────────────────────────────────────────────
    print(f"  cards rendered : {len(cards)}")
    print(f"  checks run     : {checks}")
    if fails:
        print(f"\n\033[1;31m✗ {len(fails)} problem(s)\033[0m")
        for f in fails:
            print(f"    • {f}")
        print()
        sys.exit(1)
    print("\n\033[1;32m✓ All render checks passed\033[0m\n")


if __name__ == "__main__":
    main()
