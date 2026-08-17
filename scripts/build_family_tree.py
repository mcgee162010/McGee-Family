#!/usr/bin/env python3
"""
Build levi-family-tree.html from data/family.json.

Usage:
    python3 scripts/build_family_tree.py            # validate + write HTML
    python3 scripts/build_family_tree.py --check    # validate only, no write

Edit data/family.json — never the generated HTML.
Exits non-zero on any data error so a bad tree can never be published.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "family.json"
OUT = ROOT / "levi-family-tree.html"

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# ─────────────────────────── helpers ───────────────────────────

def pretty(iso: str) -> str:
    """2019-04-07 -> Apr 7, 2019"""
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        return f"{MONTHS[m - 1]} {d}, {y}"
    except Exception:
        return iso


def die(errors: list[str]) -> None:
    print("\n\033[1;31m✗ BUILD FAILED\033[0m — fix data/family.json:\n", file=sys.stderr)
    for e in errors:
        print(f"  • {e}", file=sys.stderr)
    print(file=sys.stderr)
    sys.exit(1)


# ─────────────────────────── validation ───────────────────────────

def validate(d: dict) -> list[str]:
    """Catch every class of data error before a single byte of HTML is written."""
    errors: list[str] = []
    people: dict = d.get("people", {})
    ids = set(people)

    if not ids:
        return ["'people' is empty — nothing to build."]

    # Every person needs a name.
    for pid, p in people.items():
        if not p.get("name", "").strip():
            errors.append(f"person '{pid}' has no name")

    # Referential integrity: unions.
    for i, u in enumerate(d.get("unions", [])):
        for pid in u.get("partners", []):
            if pid not in ids:
                errors.append(f"unions[{i}] partner '{pid}' is not in people")
        for cid in u.get("children", []):
            if cid not in ids:
                errors.append(f"unions[{i}] child '{cid}' is not in people")
        if len(u.get("partners", [])) > 2:
            errors.append(f"unions[{i}] has more than 2 partners — split into separate unions")

    # Referential integrity: tiers.
    seen_in_tiers: set[str] = set()
    for t in d.get("tiers", []):
        title = t.get("title", "?")
        for row in t.get("rows", []):
            members = row if isinstance(row, list) else [row]
            for pid in members:
                if pid not in ids:
                    errors.append(f"tier '{title}' references unknown person '{pid}'")
                elif pid in seen_in_tiers:
                    errors.append(f"'{pid}' appears in more than one tier — a person belongs to exactly one row")
                else:
                    seen_in_tiers.add(pid)

    # Nobody defined but never shown (silent data rot).
    for pid in sorted(ids - seen_in_tiers):
        errors.append(f"person '{pid}' ({people[pid].get('name')}) is defined but not placed in any tier")

    # A child should not sit above its parent.
    depth = {}
    for n, t in enumerate(d.get("tiers", [])):
        for row in t.get("rows", []):
            for pid in (row if isinstance(row, list) else [row]):
                depth[pid] = n
    for i, u in enumerate(d.get("unions", [])):
        pd = [depth[p] for p in u.get("partners", []) if p in depth]
        for cid in u.get("children", []):
            if cid in depth and pd and depth[cid] <= min(pd):
                errors.append(
                    f"unions[{i}]: child '{cid}' is on the same or higher tier than its parents"
                )

    # Cycle guard: nobody may be their own ancestor.
    parent_of: dict[str, list[str]] = {}
    for u in d.get("unions", []):
        for cid in u.get("children", []):
            parent_of.setdefault(cid, []).extend(u.get("partners", []))

    def ancestors(pid: str, seen: set[str] | None = None) -> bool:
        seen = seen or set()
        if pid in seen:
            return True
        seen.add(pid)
        return any(ancestors(par, set(seen)) for par in parent_of.get(pid, []))

    for pid in ids:
        if ancestors(pid):
            errors.append(f"'{pid}' is its own ancestor — circular parent link")
            break

    return errors


# ─────────────────────────── rendering ───────────────────────────

def card(pid: str, p: dict) -> str:
    cls = "person" + "".join(f" is-{s}" for s in p.get("style", "").split() if s)
    face = p.get("face", "👤")
    if p.get("photo"):
        inner = (f'<img src="{escape(p["photo"])}" alt="{escape(p["name"])}" '
                 f'loading="lazy" decoding="async" width="62" height="62">')
    else:
        inner = face

    date_txt = ""
    if p.get("born"):
        date_txt = f"Born {pretty(p['born'])}"
    elif p.get("due"):
        date_txt = f"Due {pretty(p['due'])}"
    elif p.get("until"):
        date_txt = f"Until {pretty(p['until'])}"

    out = [f'<div class="{cls}" data-id="{escape(pid)}">',
           f'<div class="p-face">{inner}</div>',
           f'<div class="p-name">{escape(p["name"])}</div>',
           f'<div class="p-rel">{escape(p.get("rel", ""))}</div>']
    if date_txt:
        out.append(f'<div class="p-date">{date_txt}</div>')
    if p.get("badge"):
        out.append(f'<span class="badge-soon">{escape(p["badge"])}</span>')
    out.append("</div>")
    return "".join(out)


def union_label(d: dict, pair: list[str]) -> str:
    want = set(pair)
    for u in d.get("unions", []):
        if set(u.get("partners", [])) == want:
            return u.get("label", "")
    return ""


def render_tiers(d: dict) -> str:
    people = d["people"]
    blocks = []
    for i, t in enumerate(d["tiers"]):
        if i:
            blocks.append('        <div class="connector" aria-hidden="true"></div>\n')
        rows = []
        for row in t["rows"]:
            if isinstance(row, list):
                cards = "".join(card(p, people[p]) for p in row)
                lbl = union_label(d, row)
                lbl_html = f'<div class="couple-label">{escape(lbl)}</div>' if lbl else ""
                rows.append(f'            <div class="couple">{cards}{lbl_html}</div>')
            else:
                rows.append(f"            {card(row, people[row])}")
        blocks.append(
            '        <div class="gen">\n'
            f'          <div class="gen-title">{escape(t["title"])}</div>\n'
            '          <div class="row">\n'
            + "\n".join(rows) + "\n"
            "          </div>\n"
            "        </div>\n"
        )
    return "".join(blocks)


def render_facts(d: dict) -> str:
    people, unions = d["people"], d["unions"]
    ben_kids = {c for u in unions for c in u.get("children", [])
                if "ben" in u.get("partners", [])}
    cousins = sum(1 for p in people.values() if p.get("rel") == "Cousin")
    aunts = sum(1 for p in people.values() if p.get("rel") in ("Aunt", "Uncle"))
    babies = sum(1 for p in people.values() if p.get("due"))
    extended = sum(len(b["members"]) for b in d.get("branches", []))
    facts = [(cousins, "Cousins"), (aunts, "Aunts &amp; uncles"),
             (f"{extended + len(people)}+", "Relatives"), (babies, "Baby on the way")]
    cells = "".join(
        f'          <div class="fact"><b>{v}</b><span>{l}</span></div>\n' for v, l in facts
    )
    return f'        <div class="fact-strip">\n{cells}        </div>\n'


def render_branches(d: dict) -> str:
    out = []
    for b in d.get("branches", []):
        items = "".join(f"<li>{escape(m)}</li>" for m in b["members"])
        op = " open" if b.get("open") else ""
        out.append(
            f'          <details class="branch"{op}>\n'
            f'            <summary><span class="branch-emoji">{b["emoji"]}</span> {escape(b["title"])}</summary>\n'
            '            <div class="branch-body">\n'
            f'              <p class="branch-note">{escape(b.get("note", ""))}</p>\n'
            f"              <ul>{items}</ul>\n"
            "            </div>\n"
            "          </details>\n\n"
        )
    return "".join(out)


def render_open(d: dict) -> str:
    q = d.get("open_questions", [])
    if not q:
        return ""
    items = "".join(f"            <li>{escape(x)}</li>\n" for x in q)
    return (
        '        <div class="verify" style="margin-top:34px">\n'
        f"          <h3>Ben — {len(q)} item{'s' if len(q) > 1 else ''} left to confirm</h3>\n"
        f"          <ol>\n{items}          </ol>\n"
        '          <p class="branch-note" style="margin:14px 0 0">Clear <code>open_questions</code> '
        "in <code>data/family.json</code> and rebuild to remove this box.</p>\n"
        "        </div>\n"
    )


# ─────────────────────────── template ───────────────────────────

NAV = """  <nav class="nav">
    <a href="index.html" class="nav-logo"><span class="logo-icon">🌲</span> McGee Family</a>
    <ul class="nav-links">
      <li><a href="index.html">Home</a></li>
      <li><a href="family.html">Our Family</a></li>
      <li><a href="our-story.html">Our Story</a></li>
      <li><a href="gallery.html">Gallery</a></li>
      <li><a href="updates.html">Updates</a></li>
      <li><a href="events.html">Events</a></li>
      <li class="nav-more">
        <button class="nav-more-btn" aria-haspopup="true" aria-expanded="false">More ▾</button>
        <ul class="nav-dropdown" role="menu">
          <li><a href="levi-family-tree.html" role="menuitem">Levi's Family Tree</a></li>
          <li><a href="vows.html" role="menuitem">Our Vows</a></li>
          <li><a href="timeline.html" role="menuitem">Timeline</a></li>
          <li><a href="year-in-review.html" role="menuitem">Year in Review</a></li>
          <li><a href="letters.html" role="menuitem">Letters</a></li>
          <li><a href="archive.html" role="menuitem">Family Archive</a></li>
          <li><a href="bentley.html" role="menuitem">In Memory of Bentley</a></li>
          <li><a href="contact.html" role="menuitem">Contact</a></li>
        </ul>
      </li>
    </ul>
    <button class="nav-mobile-toggle" aria-label="Open navigation" aria-expanded="false">☰</button>
  </nav>"""

CSS = """    .page-hero { background: linear-gradient(160deg, var(--sage-pale) 0%, var(--cream) 60%, var(--brown-pale) 100%); padding: 72px 24px 56px; text-align: center; }
    .page-hero h1 { font-size: clamp(36px, 7vw, 68px); margin-bottom: 12px; }
    .page-hero p { font-size: 18px; color: var(--text-secondary); max-width: 560px; margin: 0 auto; }
    .tree-toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: center; margin-bottom: 34px; }
    .seg { display: inline-flex; padding: 4px; background: rgba(122,158,126,0.12); border-radius: var(--radius-full); }
    .seg button { font: inherit; font-size: 14px; font-weight: 600; color: var(--text-secondary); background: none; border: none; cursor: pointer; padding: 9px 20px; border-radius: var(--radius-full); transition: background .22s ease, color .22s ease, transform .12s ease; }
    .seg button[aria-selected="true"] { background: #fff; color: var(--forest); box-shadow: 0 2px 8px rgba(60,40,20,0.10); }
    .seg button:active { transform: scale(.97); }
    .seg button:focus-visible { outline: 3px solid var(--sage); outline-offset: 2px; }
    .gen { margin-bottom: 8px; padding: 26px 0 0; opacity: 0; transform: translateY(14px); animation: rise .55s cubic-bezier(.22,.8,.3,1) forwards; }
    .gen:nth-child(1){animation-delay:.02s}.gen:nth-child(2){animation-delay:.09s}.gen:nth-child(3){animation-delay:.16s}
    .gen:nth-child(4){animation-delay:.23s}.gen:nth-child(5){animation-delay:.30s}.gen:nth-child(6){animation-delay:.37s}
    @keyframes rise { to { opacity:1; transform:none } }
    @media (prefers-reduced-motion: reduce) { .gen { animation: none; opacity: 1; transform: none; } }
    .gen-title { display: flex; align-items: center; gap: 12px; font-size: 13px; font-weight: 600; letter-spacing: 0.10em; text-transform: uppercase; color: var(--text-tertiary); margin-bottom: 20px; }
    .gen-title::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, rgba(122,158,126,0.35), transparent); }
    .row { display: flex; flex-wrap: wrap; gap: 18px 26px; justify-content: center; }
    .couple { position: relative; display: flex; align-items: stretch; background: rgba(255,255,255,0.55); border: 1px solid rgba(122,158,126,0.20); border-radius: var(--radius-lg); padding: 12px; }
    .couple::before { content: ""; position: absolute; top: 50%; left: 50%; width: 22px; height: 2px; margin-left: -11px; background: var(--sage-light); border-radius: 2px; }
    .couple .person + .person { margin-left: 22px; }
    .couple-label { position: absolute; left: 50%; bottom: -9px; transform: translateX(-50%); background: var(--cream); padding: 0 10px; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--text-tertiary); white-space: nowrap; }
    .person { width: 152px; flex-shrink: 0; background: #fff; border: 1px solid rgba(122,158,126,0.22); border-radius: var(--radius-md); padding: 16px 12px 14px; text-align: center; box-shadow: 0 2px 10px rgba(60,40,20,0.05); transition: transform .22s cubic-bezier(.22,.8,.3,1), box-shadow .22s ease, border-color .22s ease; }
    .person:hover, .person:focus-within { transform: translateY(-3px); box-shadow: 0 10px 28px rgba(60,40,20,0.12); border-color: var(--sage); }
    .p-face { width: 62px; height: 62px; margin: 0 auto 10px; border-radius: var(--radius-full); background: var(--sage-pale); display: grid; place-items: center; font-size: 30px; overflow: hidden; border: 2px solid rgba(122,158,126,0.28); }
    .p-face img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .p-name { font-size: 14.5px; font-weight: 700; letter-spacing: -0.015em; line-height: 1.25; color: var(--text-primary); }
    .p-rel { font-size: 11px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--sage); margin-top: 5px; }
    .p-date { font-size: 11.5px; color: var(--text-tertiary); margin-top: 4px; }
    .person.is-levi { border: 2px solid var(--terracotta); background: linear-gradient(160deg, #fff, var(--terra-pale)); box-shadow: 0 6px 22px rgba(196,113,74,0.18); }
    .person.is-levi .p-rel { color: var(--terracotta); }
    .person.is-baby { border: 2px dashed var(--sage); background: linear-gradient(160deg, #fff, var(--sage-pale)); }
    .person.is-pet .p-rel { color: var(--brown-light); }
    .person.is-memory { background: var(--cream-dark); }
    .person.is-memory .p-face { filter: grayscale(1); opacity: .8; }
    .person.is-memory .p-rel { color: var(--mushroom); }
    .badge-soon { display: inline-block; margin-top: 8px; background: var(--sage); color: #fff; font-size: 10.5px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; padding: 4px 10px; border-radius: var(--radius-full); }
    .connector { width: 2px; height: 30px; margin: 0 auto; background: linear-gradient(180deg, var(--sage-light), rgba(178,205,181,0.25)); border-radius: 2px; }
    .branch-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; }
    .branch { background: rgba(255,255,255,0.72); border: 1px solid rgba(122,158,126,0.20); border-radius: var(--radius-lg); overflow: hidden; }
    .branch > summary { cursor: pointer; list-style: none; padding: 20px 22px; display: flex; align-items: center; gap: 12px; font-size: 17px; font-weight: 700; letter-spacing: -0.02em; color: var(--forest); }
    .branch > summary::-webkit-details-marker { display: none; }
    .branch > summary::after { content: "＋"; margin-left: auto; font-size: 18px; color: var(--text-tertiary); transition: transform .25s ease; }
    .branch[open] > summary::after { transform: rotate(45deg); }
    .branch > summary:focus-visible { outline: 3px solid var(--sage); outline-offset: -3px; }
    .branch-emoji { font-size: 22px; }
    .branch-body { padding: 0 22px 22px; }
    .branch-body ul { list-style: none; display: flex; flex-wrap: wrap; gap: 7px; }
    .branch-body li { background: var(--sage-pale); color: var(--text-secondary); border-radius: var(--radius-full); padding: 6px 13px; font-size: 13.5px; }
    .branch-note { font-size: 13px; color: var(--text-tertiary); margin-bottom: 12px; line-height: 1.6; }
    .verify { background: var(--brown-pale); border-left: 4px solid var(--terracotta); border-radius: var(--radius-md); padding: 24px 26px; }
    .verify h3 { font-size: 19px; color: var(--brown); margin-bottom: 10px; }
    .verify ol { margin: 0 0 0 20px; }
    .verify li { font-size: 14.5px; color: var(--text-secondary); line-height: 1.7; margin-bottom: 6px; }
    .fact-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-top: 30px; }
    .fact { background: rgba(255,255,255,0.70); border: 1px solid rgba(122,158,126,0.18); border-radius: var(--radius-md); padding: 18px 16px; text-align: center; }
    .fact b { display: block; font-size: 26px; color: var(--forest); letter-spacing: -0.02em; }
    .fact span { font-size: 12.5px; color: var(--text-tertiary); }
    [hidden] { display: none !important; }
    @media (max-width: 620px) {
      .person { width: calc(50% - 13px); min-width: 132px; }
      .couple { width: 100%; padding: 10px; }
      .couple .person + .person { margin-left: 12px; }
      .row { gap: 14px; }
    }"""

JS = """    (function () {
      var tabs = [
        { btn: document.getElementById('tab-close'), panel: document.getElementById('view-close') },
        { btn: document.getElementById('tab-ext'),   panel: document.getElementById('view-ext')   }
      ];
      function select(i) {
        tabs.forEach(function (t, n) {
          var on = n === i;
          t.btn.setAttribute('aria-selected', on ? 'true' : 'false');
          t.panel.hidden = !on;
        });
      }
      tabs.forEach(function (t, i) {
        t.btn.addEventListener('click', function () { select(i); });
        t.btn.addEventListener('keydown', function (e) {
          if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            var next = (i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
            select(next); tabs[next].btn.focus();
          }
        });
      });
    })();"""


def build(d: dict) -> str:
    m = d["meta"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="robots" content="noindex, nofollow"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>
  <meta name="description" content="Levi's family tree — the people who love him, from great-grandparents down to Baby McGee."/>
  <title>{escape(m['title'])} · McGee Family</title>
  <!-- ╔══════════════════════════════════════════════════════════════╗
       ║  GENERATED FILE — DO NOT EDIT BY HAND.                       ║
       ║  Source:  data/family.json                                   ║
       ║  Rebuild: python3 scripts/build_family_tree.py               ║
       ║  Built:   {date.today().isoformat()}                                        ║
       ╚══════════════════════════════════════════════════════════════╝ -->
  <meta property="og:type"        content="website"/>
  <meta property="og:site_name"   content="The McGee Family"/>
  <meta property="og:url"         content="https://mcgeefamily2025.com/levi-family-tree.html"/>
  <meta property="og:title"       content="{escape(m['title'])} · McGee Family"/>
  <meta property="og:description" content="Every branch, every name — the family that loves Levi."/>
  <meta name="theme-color"        content="#7A9E7E"/>
  <link rel="manifest" href="manifest.json"/>
  <meta name="mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-title" content="McGee Family"/>
  <link rel="icon" type="image/svg+xml" href="favicon.svg"/>
  <link rel="canonical" href="https://mcgeefamily2025.com/levi-family-tree.html"/>
  <link rel="stylesheet" href="css/style.css"/>
  <style>
{CSS}
  </style>
</head>
<body>

{NAV}

  <header class="page-hero">
    <h1>{escape(m['title'])}</h1>
    <p>{escape(m['intro'])}</p>
  </header>

  <main class="section">
    <div class="container">

      <div class="tree-toolbar">
        <div class="seg" role="tablist" aria-label="Choose a view">
          <button id="tab-close" role="tab" aria-selected="true"  aria-controls="view-close">Levi's Circle</button>
          <button id="tab-ext"   role="tab" aria-selected="false" aria-controls="view-ext">Everybody Else</button>
        </div>
      </div>

      <section id="view-close" role="tabpanel" aria-labelledby="tab-close">
{render_tiers(d)}
{render_facts(d)}      </section>

      <section id="view-ext" role="tabpanel" aria-labelledby="tab-ext" hidden>
        <p class="branch-note" style="text-align:center;max-width:620px;margin:0 auto 30px">
          Levi's family reaches across many branches. Tap any branch to see who's in it.
        </p>

        <div class="branch-grid">

{render_branches(d)}        </div>

{render_open(d)}      </section>

    </div>
  </main>

  <footer class="footer">
    <div class="container">
      <p class="footer-tagline">Faith. Family. Forever.</p>
      <p class="footer-note">The McGee Family · Queen Creek, Arizona</p>
    </div>
  </footer>

  <script src="js/main.js"></script>
  <script>
{JS}
  </script>
</body>
</html>
"""


# ─────────────────────────── main ───────────────────────────

def main() -> None:
    check_only = "--check" in sys.argv

    if not DATA.exists():
        die([f"{DATA.relative_to(ROOT)} not found"])

    try:
        d = json.loads(DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die([f"family.json is not valid JSON — line {e.lineno}, column {e.colno}: {e.msg}"])

    errors = validate(d)
    if errors:
        die(errors)

    n_people = len(d["people"])
    n_ext = sum(len(b["members"]) for b in d.get("branches", []))
    print(f"\033[1;32m✓ Data valid\033[0m — {n_people} in direct tree, "
          f"{n_ext} extended, {len(d['unions'])} unions, {len(d['tiers'])} tiers")

    if q := d.get("open_questions"):
        print(f"\033[1;33m⚠ {len(q)} open question(s)\033[0m — warning box will render on the page:")
        for x in q:
            print(f"    • {x}")

    if check_only:
        print("  (--check: no file written)")
        return

    OUT.write_text(build(d), encoding="utf-8")
    print(f"\033[1;32m✓ Wrote\033[0m {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")
    print("\n  Next:  git add data/family.json scripts/build_family_tree.py levi-family-tree.html")
    print('         git commit -m "Update family tree" && git push')


if __name__ == "__main__":
    main()
