#!/usr/bin/env python3
"""
Build the McGee interactive family tree from data/family.json.

Renders a dynamically-computed organic tree in SVG: tapering branch strokes,
couple pods, lineage tinting, ancestor/descendant highlighting, focus mode,
timeline view, profile drawer, dark mode, keyboard navigation.

Layout is computed client-side so collapse/expand and window resize re-flow
without a rebuild. Nothing about the tree's shape is hard-coded.

Usage:
    python3 scripts/build_family_tree.py            # validate + write
    python3 scripts/build_family_tree.py --check    # validate only
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


def pretty(iso: str) -> str:
    try:
        parts = [int(x) for x in str(iso).split("-")]
        if len(parts) == 1:
            return str(parts[0])
        if len(parts) == 2:
            return f"{MONTHS[parts[1] - 1]} {parts[0]}"
        y, m, d = parts
        return f"{MONTHS[m - 1]} {d}, {y}"
    except Exception:
        return str(iso)


def year(iso: str | None) -> str:
    if not iso:
        return ""
    return str(iso).split("-")[0]


def die(errors: list[str]) -> None:
    print("\n\033[1;31m✗ BUILD FAILED\033[0m — fix data/family.json:\n", file=sys.stderr)
    for e in errors:
        print(f"  • {e}", file=sys.stderr)
    print(file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════ validation ═══════════════════════════════

def validate(d: dict) -> list[str]:
    errors: list[str] = []
    people: dict = d.get("people", {})
    unions: list = d.get("unions", [])
    ids = set(people)

    if not ids:
        return ["'people' is empty."]
    if not unions:
        return ["'unions' is empty — at least one household is required."]

    for pid, p in people.items():
        if not str(p.get("name", "")).strip():
            errors.append(f"person '{pid}' has no name")
        # 'photo' is served over HTTP so it must be lowercase (GitHub Pages is
        # case-sensitive). 'src' is a local original used only by make_thumbs.py,
        # so its case is irrelevant — only check that it exists.
        for key in ("photo", "src"):
            photo = p.get(key)
            if not photo:
                continue
            if not (ROOT / photo).is_file():
                errors.append(f"'{pid}' {key} not found: {photo}")
            elif key == "photo" and photo != photo.lower():
                errors.append(
                    f"'{pid}' photo has uppercase characters — GitHub Pages is "
                    f"case-sensitive. Rename to lowercase: {photo}"
                )

    seen: set[str] = set()
    for i, u in enumerate(unions):
        uid = u.get("id")
        if not uid:
            errors.append(f"unions[{i}] has no 'id'")
        elif uid in seen:
            errors.append(f"duplicate union id '{uid}'")
        else:
            seen.add(uid)

        parts = u.get("partners", [])
        if not parts:
            errors.append(f"union '{uid}' has no partners")
        if len(parts) > 2:
            errors.append(f"union '{uid}' has {len(parts)} partners — max 2")
        for key in ("partners", "children", "pets"):
            for ref in u.get(key, []):
                if ref not in ids:
                    errors.append(f"union '{uid}' {key} references unknown '{ref}'")

    root = d.get("meta", {}).get("root")
    if root not in seen:
        errors.append(f"meta.root '{root}' is not a known union id")

    me = d.get("meta", {}).get("me")
    if me and me not in ids:
        errors.append(f"meta.me '{me}' is not a known person")

    placed = set()
    for u in unions:
        for key in ("partners", "children", "pets"):
            placed |= set(u.get(key, []))
    for pid in sorted(ids - placed):
        errors.append(f"'{pid}' ({people[pid].get('name')}) is in no household")

    # A child may not be its own ancestor.
    parent_of: dict[str, list[str]] = {}
    for u in unions:
        for cid in u.get("children", []):
            parent_of.setdefault(cid, []).extend(u.get("partners", []))

    def loops(pid: str, seen_: set) -> bool:
        if pid in seen_:
            return True
        seen_ = seen_ | {pid}
        return any(loops(par, seen_) for par in parent_of.get(pid, []))

    for pid in ids:
        if loops(pid, set()):
            errors.append(f"'{pid}' is its own ancestor — circular parent link")
            break

    return errors


# ═══════════════════════════════ payload ═══════════════════════════════

def payload(d: dict) -> dict:
    people, unions = d["people"], d["unions"]

    out_people = {}
    for pid, p in people.items():
        e = {"name": p["name"], "rel": p.get("rel", ""), "face": p.get("face", "👤")}
        for k in ("photo", "maiden", "place", "bio", "note", "badge", "style", "lineage"):
            if p.get(k):
                e[k] = p[k]
        if p.get("born"):
            e["born"] = p["born"]
            e["bornText"] = pretty(p["born"])
        if p.get("died"):
            e["died"] = p["died"]
            e["diedText"] = pretty(p["died"])
        if p.get("due"):
            e["due"] = p["due"]
            e["dueText"] = pretty(p["due"])
        e["deceased"] = bool(p.get("died"))
        e["expected"] = bool(p.get("due"))
        yrs = year(p.get("born"))
        yrd = year(p.get("died"))
        if yrs and yrd:
            e["life"] = f"{yrs}–{yrd}"
        elif yrs:
            e["life"] = f"b. {yrs}"
        elif p.get("due"):
            e["life"] = "due " + pretty(p["due"])
        out_people[pid] = e

    out_unions, own, birth = {}, {}, {}
    for u in unions:
        uid = u["id"]
        out_unions[uid] = {
            "id": uid,
            "partners": u.get("partners", []),
            "children": u.get("children", []),
            "pets": u.get("pets", []),
            "label": u.get("label", ""),
            "status": u.get("status", ""),
            "date": u.get("date", ""),
        }
        for pid in u.get("partners", []):
            own.setdefault(pid, []).append(uid)
        for cid in u.get("children", []):
            birth[cid] = uid

    meta = d.get("meta", {})
    return {
        "people": out_people,
        "unions": out_unions,
        "own": own,
        "birth": birth,
        "root": meta.get("root"),
        "me": meta.get("me", ""),
        "family": meta.get("family", "Our Family"),
        "branches": d.get("branches", []),
        "questions": d.get("open_questions", []),
        "lineages": d.get("lineages", {}),
    }


# ═══════════════════════════════ CSS ═══════════════════════════════

CSS = r"""
:root{
  --bark-1:#4a3728; --bark-2:#6b4f3a; --bark-3:#8a6a4f;
  --leaf-1:#3d6b52; --leaf-2:#7a9e7e; --leaf-3:#b2cdb5;
  --paper:#faf6ef; --paper-2:#f2ebdf; --paper-3:#e8dfd0;
  --ink:#2c2114; --ink-2:#5a4a3a; --ink-3:#8e7b6a;
  --accent:#c4714a; --gold:#b8944d;
  --card:#ffffff; --card-line:rgba(107,79,58,.16);
  --shadow-1:0 1px 3px rgba(60,40,20,.07),0 2px 10px rgba(60,40,20,.05);
  --shadow-2:0 6px 18px rgba(60,40,20,.11),0 18px 44px rgba(60,40,20,.08);
  --glass:rgba(250,246,239,.82);
  --branch:rgba(107,79,58,.42);
  --r-s:10px; --r-m:16px; --r-l:24px; --r-f:999px;
  --ease:cubic-bezier(.22,.9,.3,1);
  --t:.42s;
}
html[data-theme=dark]{
  --bark-1:#c8a888; --bark-2:#a88a6c; --bark-3:#8a6f55;
  --leaf-1:#7fc39b; --leaf-2:#5f9c78; --leaf-3:#3f6d54;
  --paper:#14110e; --paper-2:#1c1815; --paper-3:#26211c;
  --ink:#f4efe7; --ink-2:#c9bfb2; --ink-3:#8f8578;
  --accent:#e08b60; --gold:#d4b164;
  --card:#221d19; --card-line:rgba(244,239,231,.13);
  --shadow-1:0 1px 3px rgba(0,0,0,.4);
  --shadow-2:0 8px 24px rgba(0,0,0,.55);
  --glass:rgba(20,17,14,.8);
  --branch:rgba(200,168,136,.34);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body.tree-page{
  background:var(--paper); color:var(--ink);
  font:400 15px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",sans-serif;
  overflow:hidden; -webkit-font-smoothing:antialiased;
  transition:background var(--t) var(--ease),color var(--t) var(--ease);
}
body.tree-page.text-lg{font-size:17px}
html[data-contrast=high]{--card-line:rgba(107,79,58,.5);--ink-2:#3a2e22;--ink-3:#5a4a3a;--branch:rgba(74,55,40,.75)}
html[data-contrast=high][data-theme=dark]{--card-line:rgba(244,239,231,.45);--ink-2:#e6dfd4;--ink-3:#c2b8aa;--branch:rgba(220,196,168,.7)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px;border-radius:4px}

/* ── chrome ─────────────────────────────────────────────── */
#bar{
  position:fixed;inset:0 0 auto 0;z-index:60;display:flex;align-items:center;gap:10px;
  padding:11px 16px;background:var(--glass);
  -webkit-backdrop-filter:saturate(180%) blur(22px);backdrop-filter:saturate(180%) blur(22px);
  border-bottom:1px solid var(--card-line);
}
.brand{display:flex;align-items:baseline;gap:9px;min-width:0}
.brand h1{font:700 17px/1.1 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.02em;white-space:nowrap}
.brand .sub{font-size:11.5px;color:var(--ink-3);white-space:nowrap}
@media(max-width:720px){.brand .sub{display:none}}
.grow{flex:1 1 auto;min-width:8px}
.btn{
  font:inherit;font-size:13px;font-weight:600;color:var(--ink-2);
  background:color-mix(in srgb,var(--ink) 7%,transparent);
  border:none;border-radius:var(--r-f);padding:8px 14px;cursor:pointer;white-space:nowrap;
  display:inline-flex;align-items:center;gap:6px;
  transition:background .2s,color .2s,transform .12s;
}
.btn:hover{background:color-mix(in srgb,var(--ink) 13%,transparent)}
.btn:active{transform:scale(.96)}
.btn[aria-pressed=true],.btn.on{background:var(--leaf-1);color:#fff}
.btn.ghost{background:none}
.btn.icon{padding:8px;width:34px;height:34px;justify-content:center;font-size:15px}
.seg{display:inline-flex;padding:3px;background:color-mix(in srgb,var(--ink) 7%,transparent);border-radius:var(--r-f)}
.seg .btn{background:none;padding:6px 14px}
.seg .btn[aria-selected=true]{background:var(--card);color:var(--ink);box-shadow:var(--shadow-1)}

/* search */
.search{position:relative}
.search input{
  font:inherit;font-size:13.5px;color:var(--ink);background:var(--card);
  border:1px solid var(--card-line);border-radius:var(--r-f);
  padding:8px 14px 8px 34px;width:210px;transition:width .3s var(--ease),box-shadow .2s;
}
.search input:focus{width:260px;box-shadow:var(--shadow-1)}
.search::before{content:"⌕";position:absolute;left:13px;top:50%;transform:translateY(-52%);font-size:16px;color:var(--ink-3);pointer-events:none}
@media(max-width:640px){.search input{width:130px}.search input:focus{width:170px}}
.results{
  position:absolute;top:calc(100% + 8px);left:0;min-width:290px;max-height:340px;overflow-y:auto;
  background:var(--card);border:1px solid var(--card-line);border-radius:var(--r-m);
  box-shadow:var(--shadow-2);z-index:70;padding:5px;
}
.results:empty{display:none}
.results button{
  display:flex;align-items:center;gap:11px;width:100%;text-align:left;font:inherit;font-size:13.5px;
  background:none;border:none;padding:8px 10px;border-radius:var(--r-s);cursor:pointer;color:var(--ink);
}
.results button:hover,.results button.sel{background:color-mix(in srgb,var(--leaf-2) 18%,transparent)}
.results .av{width:34px;height:34px;border-radius:var(--r-f);overflow:hidden;flex:0 0 34px;
  background:color-mix(in srgb,var(--leaf-3) 40%,transparent);display:grid;place-items:center;font-size:17px}
.results .av img{width:100%;height:100%;object-fit:cover}
.results .nm{font-weight:600}
.results .mt{font-size:11.5px;color:var(--ink-3)}
.results .gen{margin-left:auto;font-size:10.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.05em}

/* ── stage ──────────────────────────────────────────────── */
#stage{position:fixed;inset:57px 0 0 0;overflow:hidden;touch-action:none;cursor:grab;background:
  radial-gradient(120% 80% at 50% 0%,color-mix(in srgb,var(--leaf-3) 16%,transparent),transparent 62%),
  radial-gradient(90% 60% at 50% 100%,color-mix(in srgb,var(--bark-3) 12%,transparent),transparent 60%)}
#stage.drag{cursor:grabbing}
#stage.drag *{pointer-events:none}
svg#tree{display:block;width:100%;height:100%}
.branchline{fill:none;stroke:var(--branch);stroke-linecap:round;transition:stroke .3s,stroke-width .3s,opacity .3s}
.branchline.spouse{stroke-dasharray:none}
.branchline.past{stroke-dasharray:5 6;opacity:.62}
.branchline.hot{stroke:var(--leaf-1);opacity:1}
.branchline.dim{opacity:.13}
.trunk{fill:var(--branch);opacity:.5}
.genband{fill:color-mix(in srgb,var(--ink) 3%,transparent)}
.genlabel{font:600 10px -apple-system,sans-serif;fill:var(--ink-3);letter-spacing:.14em;text-transform:uppercase}

/* ── person node ────────────────────────────────────────── */
.node{cursor:pointer;transition:opacity .34s var(--ease)}
.node.dim{opacity:.2}
.node .plate{fill:var(--card);stroke:var(--card-line);stroke-width:1;filter:url(#soft)}
.node.sel .plate{stroke:var(--accent);stroke-width:2.4}
.node.anc .plate,.node.desc .plate{stroke:var(--leaf-1);stroke-width:1.8}
.node.kin .plate{stroke:var(--leaf-2);stroke-width:1.5}
.node.me .plate{stroke:var(--gold);stroke-width:2}
.node .halo{fill:none;stroke:var(--accent);stroke-width:2;opacity:0}
.node.sel .halo{opacity:.28}
.ring{fill:color-mix(in srgb,var(--leaf-3) 40%,transparent)}
.node .nm{font:700 12.5px -apple-system,"SF Pro Text",sans-serif;fill:var(--ink);letter-spacing:-.01em}
.node .rl{font:600 9.5px -apple-system,sans-serif;fill:var(--leaf-1);letter-spacing:.06em;text-transform:uppercase}
.node .lf{font:400 10px ui-monospace,"SF Mono",monospace;fill:var(--ink-3)}
.node.gone .avatar{filter:grayscale(.85) brightness(1.03)}
.node.gone .rl{fill:var(--ink-3)}
.node .emo{font-size:26px;dominant-baseline:central;text-anchor:middle}
.pip{fill:var(--leaf-2)}
.pip.gone{fill:var(--ink-3)}
.node .plus{fill:var(--leaf-1);transition:transform .3s var(--ease)}
.node .plusgl{fill:#fff;font:700 12px -apple-system,sans-serif;text-anchor:middle;dominant-baseline:central}
.node.open .plus{fill:var(--accent)}
.badge{fill:var(--leaf-2)}
.badge-t{fill:#fff;font:700 8px -apple-system,sans-serif;text-anchor:middle;dominant-baseline:central;letter-spacing:.05em}
.podlabel{font:600 9.5px -apple-system,sans-serif;fill:var(--ink-3);letter-spacing:.05em;text-transform:uppercase;text-anchor:middle}
.podlabel.past{fill:var(--ink-3);font-style:italic}

/* ── floating controls ──────────────────────────────────── */
#dock{position:fixed;right:14px;bottom:14px;z-index:55;display:flex;flex-direction:column;gap:7px;align-items:flex-end}
#dock .grp{display:flex;flex-direction:column;background:var(--glass);
  -webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);
  border:1px solid var(--card-line);border-radius:var(--r-m);overflow:hidden;box-shadow:var(--shadow-1)}
#dock .grp .btn{border-radius:0;background:none;width:40px;height:38px;padding:0;justify-content:center;font-size:16px}
#dock .grp .btn+.btn{border-top:1px solid var(--card-line)}
#dock .wide{border-radius:var(--r-f);background:var(--glass);border:1px solid var(--card-line);
  -webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);box-shadow:var(--shadow-1)}
@media(max-width:640px){#dock{right:10px;bottom:calc(10px + env(safe-area-inset-bottom))}}

#hint{position:fixed;left:50%;transform:translateX(-50%);bottom:16px;z-index:50;
  font-size:12.5px;color:var(--ink-3);background:var(--glass);padding:7px 15px;border-radius:var(--r-f);
  border:1px solid var(--card-line);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);
  pointer-events:none;transition:opacity .5s}
#hint.hide{opacity:0}
@media(max-width:640px){#hint{display:none}}

#crumb{position:fixed;left:16px;top:68px;z-index:50;display:flex;align-items:center;gap:8px;
  font-size:12px;color:var(--ink-2);background:var(--glass);padding:7px 13px;border-radius:var(--r-f);
  border:1px solid var(--card-line);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);
  max-width:calc(100vw - 32px);opacity:0;transform:translateY(-6px);transition:opacity .3s,transform .3s;pointer-events:none}
#crumb.on{opacity:1;transform:none;pointer-events:auto}
#crumb b{color:var(--ink)}
#crumb .x{background:none;border:none;cursor:pointer;color:var(--ink-3);font-size:14px;padding:0 2px}

/* ── drawer ─────────────────────────────────────────────── */
#drawer{
  position:fixed;top:57px;right:0;bottom:0;width:378px;z-index:58;
  background:var(--glass);-webkit-backdrop-filter:saturate(180%) blur(26px);backdrop-filter:saturate(180%) blur(26px);
  border-left:1px solid var(--card-line);box-shadow:-14px 0 44px rgba(60,40,20,.11);
  transform:translateX(100%);transition:transform var(--t) var(--ease);
  overflow-y:auto;overscroll-behavior:contain;padding:22px 22px 40px;
}
#drawer.on{transform:none}
@media(max-width:760px){
  #drawer{top:auto;left:0;width:auto;max-height:86vh;border-left:none;border-top:1px solid var(--card-line);
    border-radius:var(--r-l) var(--r-l) 0 0;transform:translateY(101%);
    padding-bottom:calc(40px + env(safe-area-inset-bottom));box-shadow:0 -14px 44px rgba(0,0,0,.2)}
}
.grip{width:38px;height:4px;border-radius:2px;background:var(--card-line);margin:0 auto 16px;display:none}
@media(max-width:760px){.grip{display:block}}
.dclose{position:absolute;top:18px;right:18px;width:30px;height:30px;border-radius:var(--r-f);border:none;
  background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--ink-2);cursor:pointer;font-size:14px}
.dhero{display:flex;gap:14px;align-items:flex-start;margin:0 34px 16px 0}
.dav{width:76px;height:76px;border-radius:var(--r-m);overflow:hidden;flex:0 0 76px;
  background:color-mix(in srgb,var(--leaf-3) 40%,transparent);display:grid;place-items:center;font-size:34px;
  box-shadow:var(--shadow-1)}
.dav img{width:100%;height:100%;object-fit:cover}
.dav.gone img{filter:grayscale(.85)}
.dhero h2{font:700 21px/1.15 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.022em}
.dhero .maiden{font-size:12.5px;color:var(--ink-3);font-style:italic;margin-top:2px}
.dhero .rl{font:600 10.5px -apple-system,sans-serif;color:var(--leaf-1);letter-spacing:.07em;text-transform:uppercase;margin-top:6px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{font-size:11px;font-weight:600;padding:4px 9px;border-radius:var(--r-f);
  background:color-mix(in srgb,var(--leaf-2) 16%,transparent);color:var(--ink-2)}
.chip.mem{background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--ink-3)}
.chip.soon{background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent)}
.dbio{font-size:14px;line-height:1.62;color:var(--ink-2);margin-bottom:18px}
.dsec{margin-bottom:18px}
.dsec h3{font:600 10.5px -apple-system,sans-serif;color:var(--ink-3);letter-spacing:.12em;
  text-transform:uppercase;margin-bottom:9px;display:flex;align-items:center;gap:8px}
.dsec h3::after{content:"";flex:1;height:1px;background:var(--card-line)}
.dl{display:grid;gap:7px}
.dl .row{display:flex;gap:10px;font-size:13.5px;align-items:baseline}
.dl dt{flex:0 0 82px;color:var(--ink-3);font-weight:600;font-size:12px}
.dl dd{margin:0;color:var(--ink-2)}
.lnk{font:inherit;font-size:13.5px;color:var(--leaf-1);background:none;border:none;padding:0;cursor:pointer;
  text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--leaf-1) 34%,transparent);text-underline-offset:2px}
.lnk:hover{text-decoration-color:var(--leaf-1)}
.minitree{background:var(--card);border:1px solid var(--card-line);border-radius:var(--r-m);padding:14px 12px}
.minitree svg{width:100%;height:auto;display:block}
.mt-n{font:600 9.5px -apple-system,sans-serif;fill:var(--ink);text-anchor:middle}
.mt-l{stroke:var(--branch);fill:none;stroke-width:1.2}
.mt-c{fill:color-mix(in srgb,var(--leaf-3) 45%,transparent);stroke:var(--card-line)}
.mt-c.self{fill:color-mix(in srgb,var(--accent) 26%,transparent);stroke:var(--accent)}
.dact{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}

/* ── timeline ───────────────────────────────────────────── */
#timeline{position:fixed;inset:57px 0 0 0;z-index:40;overflow-y:auto;background:var(--paper);
  padding:34px 20px 80px;display:none}
#timeline.on{display:block}
.tl{max-width:720px;margin:0 auto;position:relative}
.tl::before{content:"";position:absolute;left:78px;top:6px;bottom:6px;width:2px;
  background:linear-gradient(180deg,transparent,var(--branch) 6%,var(--branch) 94%,transparent)}
.tlrow{display:flex;gap:20px;align-items:flex-start;padding:9px 0;position:relative}
.tlyr{flex:0 0 62px;text-align:right;font:700 13px ui-monospace,"SF Mono",monospace;color:var(--ink-3);padding-top:11px}
.tldot{position:absolute;left:73px;top:19px;width:11px;height:11px;border-radius:var(--r-f);
  background:var(--card);border:2.5px solid var(--leaf-2)}
.tldot.d{border-color:var(--ink-3)}
.tldot.m{border-color:var(--gold)}
.tldot.s{border-color:var(--accent)}
.tlcard{flex:1;margin-left:26px;background:var(--card);border:1px solid var(--card-line);
  border-radius:var(--r-m);padding:12px 15px;box-shadow:var(--shadow-1);cursor:pointer;
  display:flex;align-items:center;gap:12px;text-align:left;font:inherit;color:var(--ink);width:100%}
.tlcard:hover{box-shadow:var(--shadow-2);transform:translateY(-1px)}
.tlcard .av{width:38px;height:38px;border-radius:var(--r-f);overflow:hidden;flex:0 0 38px;
  background:color-mix(in srgb,var(--leaf-3) 40%,transparent);display:grid;place-items:center;font-size:19px}
.tlcard .av img{width:100%;height:100%;object-fit:cover}
.tlcard .ev{font-size:11px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.tlcard .who{font-weight:700;font-size:14.5px;letter-spacing:-.01em}
.tlhead{text-align:center;margin-bottom:26px}
.tlhead h2{font:700 25px -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.022em}
.tlhead p{color:var(--ink-3);font-size:14px;margin-top:5px}

/* ── more family ────────────────────────────────────────── */
#more{position:fixed;inset:57px 0 0 0;z-index:40;overflow-y:auto;background:var(--paper);
  padding:34px 20px 80px;display:none}
#more.on{display:block}
.mwrap{max-width:860px;margin:0 auto}
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(258px,1fr));gap:14px}
.mb{background:var(--card);border:1px solid var(--card-line);border-radius:var(--r-l);overflow:hidden}
.mb summary{cursor:pointer;list-style:none;padding:16px 19px;display:flex;align-items:center;gap:11px;
  font:700 15.5px -apple-system,sans-serif;color:var(--ink);letter-spacing:-.015em}
.mb summary::-webkit-details-marker{display:none}
.mb summary::after{content:"＋";margin-left:auto;color:var(--ink-3);transition:transform .25s}
.mb[open] summary::after{transform:rotate(45deg)}
.mb ul{list-style:none;display:flex;flex-wrap:wrap;gap:6px;padding:0 19px 19px}
.mb li{background:color-mix(in srgb,var(--leaf-2) 14%,transparent);color:var(--ink-2);
  border-radius:var(--r-f);padding:5px 12px;font-size:13px}
.qn{max-width:640px;margin:26px auto 0;background:color-mix(in srgb,var(--accent) 11%,transparent);
  border-left:3px solid var(--accent);border-radius:var(--r-s);padding:15px 18px;font-size:13.5px;
  color:var(--ink-2);line-height:1.6}

@media(prefers-reduced-motion:reduce){
  *{animation-duration:.001s!important;transition-duration:.001s!important}
}
html[data-motion=off] *{animation:none!important;transition:none!important}
"""


# ═══════════════════════════════ JS ═══════════════════════════════

JS = r"""
(function(){
'use strict';
var G=window.__FAMILY__, P=G.people, U=G.unions, OWN=G.own, BIRTH=G.birth;
var LIN=G.lineages||{};

/* ---------- geometry constants ---------- */
var NW=140, NH=62, GAPX=26, GAPY=118, PODGAP=16;

var svg=document.getElementById('tree'),
    gLink=document.getElementById('links'),
    gNode=document.getElementById('nodes'),
    gBand=document.getElementById('bands'),
    world=document.getElementById('world'),
    stage=document.getElementById('stage'),
    drawer=document.getElementById('drawer'),
    crumb=document.getElementById('crumb');

var S={sel:null,open:{},collapsed:{},focus:false,colors:true,view:'tree',lod:false};
var pos={}, gen={}, order=[], hidden={}, laid=false;
var BIG=140;   /* above this many people, distant branches auto-collapse */

function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function el(t,a){var n=document.createElementNS('http://www.w3.org/2000/svg',t);
  for(var k in a)n.setAttribute(k,a[k]);return n;}

/* ═══════════ relationship helpers ═══════════ */
function partnerUnions(pid){return OWN[pid]||[];}
function spouses(pid){var o=[];partnerUnions(pid).forEach(function(u){
  U[u].partners.forEach(function(x){if(x!==pid&&o.indexOf(x)<0)o.push(x);});});return o;}
function kids(pid){var o=[];partnerUnions(pid).forEach(function(u){
  (U[u].children||[]).forEach(function(c){if(o.indexOf(c)<0)o.push(c);});});return o;}
function parents(pid){var b=BIRTH[pid];return b?U[b].partners.slice():[];}
function siblings(pid){var b=BIRTH[pid];if(!b)return [];
  return (U[b].children||[]).filter(function(c){return c!==pid;});}

function ancestors(pid){var out={},q=parents(pid);
  while(q.length){var x=q.pop();if(out[x])continue;out[x]=1;parents(x).forEach(function(p){q.push(p);});}
  return out;}
function descendants(pid){var out={},q=kids(pid);
  while(q.length){var x=q.pop();if(out[x])continue;out[x]=1;kids(x).forEach(function(c){q.push(c);});}
  return out;}

function generationOf(pid){return gen[pid]||0;}

/* ═══════════ generation assignment ═══════════ */
function computeGen(){
  gen={};
  Object.keys(P).forEach(function(p){if(!BIRTH[p])gen[p]=0;});
  for(var i=0;i<60;i++){
    var moved=false;
    Object.keys(U).forEach(function(uid){
      var u=U[uid], g=0;
      u.partners.forEach(function(p){if((gen[p]||0)>g)g=gen[p]||0;});
      u.partners.forEach(function(p){if((gen[p]||0)!==g){gen[p]=g;moved=true;}});
      (u.children||[]).forEach(function(c){if((gen[c]||0)<g+1){gen[c]=g+1;moved=true;}});
      (u.pets||[]).forEach(function(c){if((gen[c]||0)<g+1){gen[c]=g+1;moved=true;}});
    });
    if(!moved)break;
  }
  Object.keys(P).forEach(function(p){if(gen[p]==null)gen[p]=0;});
}

/* ═══════════ layout engine ═══════════
   Person-centric tidy layout. Each person is placed once. A "pod" is a person
   plus the spouses they are shown beside. Children hang from the pod centre.
   Subtrees are packed left-to-right against a rising cursor, then pods are
   centred over their children. This keeps lineage vertical and avoids overlap
   without needing crossing-line heuristics. ---------------------------------*/
function layout(){
  computeGen();
  pos={};order=[];hidden={};
  var total=Object.keys(P).length;

  /* Level-of-detail: on very large trees, collapse branches far from the
     focal person so the layout stays readable. Users expand by tapping. */
  if(total>BIG&&!S.lod){
    S.lod=true;
    var anchor=S.sel||G.me||U[G.root].partners[0];
    var near={};near[anchor]=1;
    Object.keys(ancestors(anchor)).forEach(function(k){near[k]=1;});
    Object.keys(descendants(anchor)).forEach(function(k){near[k]=1;});
    siblings(anchor).forEach(function(k){near[k]=1;});
    spouses(anchor).forEach(function(k){near[k]=1;});
    Object.keys(P).forEach(function(p){
      if(!near[p]&&kids(p).length>2&&S.collapsed[p]===undefined)S.collapsed[p]=true;
    });
  }

  /* mark everything beneath a collapsed person as hidden */
  Object.keys(S.collapsed).forEach(function(p){
    if(!S.collapsed[p])return;
    Object.keys(descendants(p)).forEach(function(d){hidden[d]=1;});
  });

  var done={}, cursor=0;

  /* A person seeds their own pod only if they are a blood descendant in this
     tree (they have parents here) OR they have children. Married-in partners
     with no children of their own get absorbed into their spouse's pod, which
     is what stops the layout sprawling into one flat ribbon of root pods. */
  function seedsOwnPod(pid){
    if(BIRTH[pid])return true;
    if(kids(pid).length)return true;
    return spouses(pid).length===0;
  }

  function podMembers(pid){
    var m=[pid];
    partnerUnions(pid).forEach(function(u){
      U[u].partners.forEach(function(x){
        if(x===pid||done[x]||hidden[x]||m.indexOf(x)>-1)return;
        if(!seedsOwnPod(x))m.push(x);
      });
    });
    return m;
  }

  function place(pid){
    if(done[pid]||hidden[pid])return null;
    var mem=podMembers(pid);
    mem.forEach(function(m){done[m]=1;});
    var w=mem.length*NW+(mem.length-1)*PODGAP;

    var ch=[];
    if(!S.collapsed[pid]){
      partnerUnions(pid).forEach(function(u){
        (U[u].children||[]).forEach(function(c){if(!done[c]&&!hidden[c])ch.push(c);});
        (U[u].pets||[]).forEach(function(c){if(!done[c]&&!hidden[c])ch.push(c);});
      });
    }

    var left;
    if(!ch.length){
      left=cursor;
    }else{
      var spans=ch.map(place).filter(Boolean);
      if(!spans.length){left=cursor;}
      else{
        var c=(spans[0].l+spans[spans.length-1].r)/2;
        left=Math.max(cursor,c-w/2);
      }
    }
    cursor=Math.max(cursor,left+w+GAPX);
    mem.forEach(function(m,i){
      pos[m]={x:left+i*(NW+PODGAP),y:generationOf(m)*(NH+GAPY),pod:pid,idx:i};
      order.push(m);
    });
    return {l:left,r:left+w};
  }

  /* Roots: blood-line ancestors first (parentless people who have children),
     shallowest generation first so their subtrees pack cleanly. Married-in
     partners are absorbed by podMembers, then the final sweep catches strays. */
  Object.keys(P)
    .filter(function(p){return !BIRTH[p]&&!hidden[p]&&kids(p).length;})
    .sort(function(a,b){return generationOf(a)-generationOf(b);})
    .forEach(place);
  Object.keys(P).forEach(place);
  laid=true;
}

/* ═══════════ drawing ═══════════ */
function lineageOf(pid){
  var p=P[pid];
  if(p.lineage)return p.lineage;
  var a=ancestors(pid),k=Object.keys(a);
  for(var i=0;i<k.length;i++){if(P[k[i]].lineage)return P[k[i]].lineage;}
  return '';
}
function tint(pid){
  if(!S.colors)return null;
  var l=lineageOf(pid);
  return l&&LIN[l]?LIN[l]:null;
}

/* organic tapering branch: cubic bezier, thicker near the parent */
function branch(x1,y1,x2,y2,gN){
  var my=(y1+y2)/2, bow=Math.min(38,Math.abs(x2-x1)*.34);
  return 'M'+x1+' '+y1+
         'C'+x1+' '+(my-bow*.25)+' '+x2+' '+(my+bow*.25)+' '+x2+' '+y2;
}
function widthFor(g){return Math.max(1.3,4.6-g*.62);}

function draw(){
  gLink.textContent='';gNode.textContent='';gBand.textContent='';

  /* generation bands + labels */
  var maxG=0;Object.keys(gen).forEach(function(p){if(gen[p]>maxG)maxG=gen[p];});
  var xs=Object.keys(pos).map(function(p){return pos[p].x;});
  var minX=Math.min.apply(null,xs)-90, maxX=Math.max.apply(null,xs)+NW+90;
  var names=G.genNames||[];
  for(var g=0;g<=maxG;g++){
    var y=g*(NH+GAPY);
    if(g%2===1)gBand.appendChild(el('rect',{class:'genband',x:minX,y:y-24,
      width:maxX-minX,height:NH+48,rx:18}));
    var t=el('text',{class:'genlabel',x:minX+10,y:y-30});
    t.textContent=(names[g]||('Generation '+(g+1)));
    gBand.appendChild(t);
  }

  /* trunk behind generation 0 */
  var g0=Object.keys(pos).filter(function(p){return gen[p]===0;});
  if(g0.length){
    var cx=g0.reduce(function(a,p){return a+pos[p].x+NW/2;},0)/g0.length;
    gBand.appendChild(el('path',{class:'trunk',d:
      'M'+(cx-13)+' '+(-16)+' C'+(cx-7)+' '+(maxG*(NH+GAPY)*.5)+' '+(cx-9)+' '+
      (maxG*(NH+GAPY)*.8)+' '+(cx-5)+' '+(maxG*(NH+GAPY)+NH)+
      ' L'+(cx+5)+' '+(maxG*(NH+GAPY)+NH)+' C'+(cx+9)+' '+(maxG*(NH+GAPY)*.8)+' '+
      (cx+7)+' '+(maxG*(NH+GAPY)*.5)+' '+(cx+13)+' '+(-16)+' Z'}));
  }

  /* links */
  Object.keys(U).forEach(function(uid){
    var u=U[uid], ps=u.partners.filter(function(p){return pos[p];});
    var mx=null,my=null;
    if(ps.length===2){
      var a=pos[ps[0]],b=pos[ps[1]];
      var l=a.x<b.x?a:b, r=a.x<b.x?b:a;
      var yy=l.y+NH*.42;
      gLink.appendChild(el('path',{class:'branchline spouse'+(u.status==='past'?' past':''),
        d:'M'+(l.x+NW)+' '+yy+'H'+r.x,'stroke-width':2.1,'data-u':uid}));
      mx=(l.x+NW+r.x)/2;my=l.y+NH;
    }else if(ps.length===1){var a1=pos[ps[0]];mx=a1.x+NW/2;my=a1.y+NH;}

    var ch=(u.children||[]).concat(u.pets||[]).filter(function(c){return pos[c];});
    if(!ch.length)return;
    var ky=Math.min.apply(null,ch.map(function(c){return pos[c].y;}));
    var bus=ky-GAPY*.46;
    var gg=gen[ps[0]]||0;
    if(mx!==null)gLink.appendChild(el('path',{class:'branchline',
      d:'M'+mx+' '+my+'V'+bus,'stroke-width':widthFor(gg),'data-u':uid}));
    ch.forEach(function(c){
      var k=pos[c],kx=k.x+NW/2;
      gLink.appendChild(el('path',{class:'branchline',
        d:branch(mx!==null?mx:kx,bus,kx,k.y),'stroke-width':widthFor(gg+1),
        'data-u':uid,'data-c':c}));
    });
  });

  /* pod labels */
  Object.keys(U).forEach(function(uid){
    var u=U[uid];if(!u.label)return;
    var ps=u.partners.filter(function(p){return pos[p];});
    if(ps.length<1)return;
    var xsum=0;ps.forEach(function(p){xsum+=pos[p].x+NW/2;});
    var t=el('text',{class:'podlabel'+(u.status==='past'?' past':''),
      x:xsum/ps.length,y:pos[ps[0]].y+NH+15});
    t.textContent=u.label;gLink.appendChild(t);
  });

  /* nodes */
  order.forEach(function(pid){
    var p=P[pid],q=pos[pid];if(!q)return;
    var cls='node'+(p.deceased?' gone':'')+(pid===G.me?' me':'')+(S.open[pid]?' open':'');
    var g=el('g',{class:cls,transform:'translate('+q.x+','+q.y+')',
      'data-id':pid,tabindex:'0',role:'button',
      'aria-label':p.name+', '+p.rel+(p.life?', '+p.life:'')});

    g.appendChild(el('rect',{class:'halo',x:-4,y:-4,width:NW+8,height:NH+8,rx:16}));
    var plate=el('rect',{class:'plate',width:NW,height:NH,rx:13});
    var t=tint(pid);
    if(t)plate.setAttribute('style','fill:color-mix(in srgb,'+t+' 8%,var(--card))');
    g.appendChild(plate);

    /* avatar */
    var cx=NH/2, r=20;
    g.appendChild(el('circle',{class:'ring',cx:cx,cy:NH/2,r:r}));
    if(p.photo){
      var cid='c'+pid.replace(/[^a-z0-9]/gi,'');
      var cp=el('clipPath',{id:cid});
      cp.appendChild(el('circle',{cx:cx,cy:NH/2,r:r}));
      g.appendChild(cp);
      var im=el('image',{class:'avatar',x:cx-r,y:NH/2-r,width:r*2,height:r*2,
        'clip-path':'url(#'+cid+')',preserveAspectRatio:'xMidYMid slice'});
      im.setAttributeNS('http://www.w3.org/1999/xlink','href',p.photo);
      im.setAttribute('href',p.photo);
      g.appendChild(im);
    }else{
      var e=el('text',{class:'emo',x:cx,y:NH/2+1});e.textContent=p.face;g.appendChild(e);
    }
    /* living / deceased pip */
    g.appendChild(el('circle',{class:'pip'+(p.deceased?' gone':''),cx:cx+r-3,cy:NH/2+r-6,r:3.4}));

    /* text */
    var tx=NH/2+r+4;
    var nm=el('text',{class:'nm',x:tx,y:24});
    nm.textContent=p.name.length>17?p.name.slice(0,16)+'…':p.name;g.appendChild(nm);
    var rl=el('text',{class:'rl',x:tx,y:37});rl.textContent=p.rel;g.appendChild(rl);
    if(p.life){var lf=el('text',{class:'lf',x:tx,y:50});lf.textContent=p.life;g.appendChild(lf);}

    if(p.badge){
      var bw=p.badge.length*5.1+14;
      g.appendChild(el('rect',{class:'badge',x:NW-bw-7,y:-7,width:bw,height:15,rx:7.5}));
      var bt=el('text',{class:'badge-t',x:NW-bw/2-7,y:.7});bt.textContent=p.badge;g.appendChild(bt);
    }

    /* collapse / expand affordance — only when the person actually has kids */
    var kc=kids(pid).length;
    if(kc){
      var open=!S.collapsed[pid];
      var cw=open?18:30;
      g.appendChild(el('rect',{class:'plus',x:NW/2-cw/2,y:NH-7,width:cw,height:16,rx:8,
        'data-toggle':pid}));
      var ct=el('text',{class:'plusgl',x:NW/2,y:NH+1.4,'data-toggle':pid});
      ct.textContent=open?'−':'+'+kc;
      g.appendChild(ct);
    }

    g.appendChild(el('title')).textContent=p.name+(p.note?' — '+p.note:'');
    gNode.appendChild(g);
  });

  applyEmphasis();
}

/* ═══════════ emphasis ═══════════ */
function applyEmphasis(){
  var nodes=gNode.querySelectorAll('.node'), links=gLink.querySelectorAll('.branchline');
  if(!S.sel){
    nodes.forEach(function(n){n.classList.remove('dim','sel','anc','desc','kin');});
    links.forEach(function(l){l.classList.remove('dim','hot');});
    crumb.classList.remove('on');
    return;
  }
  var id=S.sel, A=ancestors(id), D=descendants(id);
  var kin={};spouses(id).forEach(function(x){kin[x]=1;});siblings(id).forEach(function(x){kin[x]=1;});
  var keep={};keep[id]=1;
  Object.keys(A).forEach(function(k){keep[k]=1;});
  Object.keys(D).forEach(function(k){keep[k]=1;});
  Object.keys(kin).forEach(function(k){keep[k]=1;});
  // spouses of descendants keep context for their children
  Object.keys(D).forEach(function(k){spouses(k).forEach(function(s){keep[s]=1;});});
  Object.keys(A).forEach(function(k){spouses(k).forEach(function(s){keep[s]=1;});});

  nodes.forEach(function(n){
    var i=n.dataset.id;
    n.classList.toggle('sel',i===id);
    n.classList.toggle('anc',!!A[i]);
    n.classList.toggle('desc',!!D[i]);
    n.classList.toggle('kin',!!kin[i]&&i!==id);
    n.classList.toggle('dim',!keep[i]);
  });
  links.forEach(function(l){
    var u=U[l.dataset.u];
    var on=u&&u.partners.concat(u.children||[],u.pets||[]).some(function(x){return keep[x];});
    l.classList.toggle('hot',!!on);
    l.classList.toggle('dim',!on);
  });

  var p=P[id];
  crumb.innerHTML='<span>Viewing</span><b>'+esc(p.name)+'</b>'+
    '<span>· '+Object.keys(A).length+' ancestors · '+Object.keys(D).length+' descendants</span>'+
    '<button class="x" aria-label="Clear selection">✕</button>';
  crumb.querySelector('.x').onclick=function(){select(null);};
  crumb.classList.add('on');
}

/* ═══════════ view transform ═══════════ */
var vx=0,vy=0,vk=1;
function apply(){world.setAttribute('transform','translate('+vx+','+vy+') scale('+vk+')');}
function bbox(ids){
  var list=ids||Object.keys(pos);
  if(!list.length)return null;
  var x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  list.forEach(function(p){var q=pos[p];if(!q)return;
    x0=Math.min(x0,q.x);y0=Math.min(y0,q.y);x1=Math.max(x1,q.x+NW);y1=Math.max(y1,q.y+NH);});
  return {x0:x0-70,y0:y0-80,x1:x1+70,y1:y1+70};
}
function animateTo(nx,ny,nk,ms){
  if(document.documentElement.dataset.motion==='off'||
     window.matchMedia('(prefers-reduced-motion:reduce)').matches){vx=nx;vy=ny;vk=nk;apply();return;}
  var sx=vx,sy=vy,sk=vk,t0=performance.now();ms=ms||520;
  (function step(t){
    var u=Math.min(1,(t-t0)/ms), e=1-Math.pow(1-u,3);
    vx=sx+(nx-sx)*e;vy=sy+(ny-sy)*e;vk=sk+(nk-sk)*e;apply();
    if(u<1)requestAnimationFrame(step);
  })(t0);
}
function fitTo(ids,pad,ms){
  var b=bbox(ids);if(!b)return;
  var r=stage.getBoundingClientRect();
  pad=pad||1;
  var k=Math.min(r.width/(b.x1-b.x0),r.height/(b.y1-b.y0))*pad;
  /* Legibility floor: 12.5px name text must never render below ~9px, or the
     tree becomes dust. A wide shallow family would otherwise fit at 0.27.
     Past the floor we keep type readable and let the user pan — same tradeoff
     Maps makes. */
  k=Math.max(.75,Math.min(k,1.55));
  animateTo(r.width/2-((b.x0+b.x1)/2)*k, r.height/2-((b.y0+b.y1)/2)*k, k, ms);
}
function fitAll(ms){
  /* True fit-all, allowed to go small — this is an explicit user request. */
  var b=bbox(null);if(!b)return;
  var r=stage.getBoundingClientRect();
  var k=Math.min(r.width/(b.x1-b.x0),r.height/(b.y1-b.y0))*.94;
  k=Math.max(.14,Math.min(k,1.4));
  animateTo(r.width/2-((b.x0+b.x1)/2)*k, r.height/2-((b.y0+b.y1)/2)*k, k, ms);
}
/* The default view: the home household plus one generation each way, at a
   scale where faces and names are actually readable. */
function homeView(ms){
  var u=U[G.root], set=u.partners.slice();
  u.partners.forEach(function(p){
    parents(p).forEach(function(x){set.push(x);});
    spouses(p).forEach(function(x){set.push(x);});
  });
  (u.children||[]).concat(u.pets||[]).forEach(function(c){set.push(c);});
  set=set.filter(function(p){return pos[p];});
  fitTo(set.length?set:null,.82,ms);
}
function centerOn(id,ms){
  var q=pos[id];if(!q)return;
  var r=stage.getBoundingClientRect(), k=Math.max(vk,.82);
  animateTo(r.width/2-(q.x+NW/2)*k, r.height*.42-(q.y+NH/2)*k, k, ms);
}

/* pan + zoom */
var drag=null;
stage.addEventListener('pointerdown',function(e){
  if(e.target.closest('.node'))return;
  drag={x:e.clientX-vx,y:e.clientY-vy};stage.classList.add('drag');
  try{stage.setPointerCapture(e.pointerId);}catch(_){}
});
stage.addEventListener('pointermove',function(e){
  if(!drag)return;vx=e.clientX-drag.x;vy=e.clientY-drag.y;apply();});
function endDrag(){drag=null;stage.classList.remove('drag');}
stage.addEventListener('pointerup',endDrag);
stage.addEventListener('pointercancel',endDrag);
stage.addEventListener('wheel',function(e){
  e.preventDefault();
  var f=Math.exp(-e.deltaY*(e.ctrlKey?.011:.0021));
  zoomAt(e.clientX,e.clientY,Math.min(3.2,Math.max(.1,vk*f)));
},{passive:false});
function zoomAt(cx,cy,k){
  var r=stage.getBoundingClientRect();
  cx-=r.left;cy-=r.top;
  vx=cx-(cx-vx)*(k/vk);vy=cy-(cy-vy)*(k/vk);vk=k;apply();
}
/* pinch */
var pts={},pd0=0,pk0=1;
stage.addEventListener('pointerdown',function(e){pts[e.pointerId]=e;});
stage.addEventListener('pointermove',function(e){
  if(!(e.pointerId in pts))return;pts[e.pointerId]=e;
  var k=Object.keys(pts);if(k.length!==2)return;
  var a=pts[k[0]],b=pts[k[1]];
  var d=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);
  if(!pd0){pd0=d;pk0=vk;return;}
  drag=null;
  zoomAt((a.clientX+b.clientX)/2,(a.clientY+b.clientY)/2,
    Math.min(3.2,Math.max(.1,pk0*d/pd0)));
});
function clearPt(e){delete pts[e.pointerId];if(Object.keys(pts).length<2)pd0=0;}
stage.addEventListener('pointerup',clearPt);
stage.addEventListener('pointercancel',clearPt);
stage.addEventListener('dblclick',function(e){
  if(e.target.closest('.node'))return;
  zoomAt(e.clientX,e.clientY,Math.min(3.2,vk*1.6));
});

/* ═══════════ selection ═══════════ */
function select(id,opts){
  opts=opts||{};
  if(id&&S.sel===id&&!opts.keep){S.sel=null;applyEmphasis();if(S.focus)homeView();return;}
  S.sel=id;
  applyEmphasis();
  if(id){
    if(S.focus){
      var set=[id].concat(Object.keys(ancestors(id)),Object.keys(descendants(id)),
        spouses(id),siblings(id));
      fitTo(set,.86);
    }else if(opts.center)centerOn(id);
  }
}

gNode.addEventListener('click',function(e){
  var t=e.target.closest('[data-toggle]');
  if(t){
    var id=t.getAttribute('data-toggle');
    S.collapsed[id]=!S.collapsed[id];
    layout();draw();
    return;
  }
  var n=e.target.closest('.node');if(!n)return;
  select(n.dataset.id,{center:true});
});
gNode.addEventListener('dblclick',function(e){
  var n=e.target.closest('.node');if(!n)return;
  e.stopPropagation();openProfile(n.dataset.id);
});
gNode.addEventListener('keydown',function(e){
  var n=e.target.closest('.node');if(!n)return;
  var id=n.dataset.id;
  if(e.key==='Enter'||e.key===' '){e.preventDefault();select(id,{center:true});return;}
  if(e.key==='i'||e.key==='I'){e.preventDefault();openProfile(id);return;}
  var to=null;
  if(e.key==='ArrowUp')to=parents(id)[0];
  if(e.key==='ArrowDown')to=kids(id)[0];
  if(e.key==='ArrowLeft'||e.key==='ArrowRight'){
    var sib=BIRTH[id]?(U[BIRTH[id]].children||[]):[];
    var i=sib.indexOf(id);
    if(i>=0)to=sib[i+(e.key==='ArrowRight'?1:-1)];
    if(!to){var sp=spouses(id);to=sp[0];}
  }
  if(to&&pos[to]){e.preventDefault();
    var t=gNode.querySelector('.node[data-id="'+to+'"]');
    if(t){t.focus();select(to,{center:true});}}
});

/* ═══════════ profile drawer ═══════════ */
function openProfile(id){
  var p=P[id];if(!p)return;
  select(id,{keep:true,center:true});
  var A=ancestors(id),D=descendants(id);
  var rows='';
  function link(x){return '<button class="lnk" data-goto="'+esc(x)+'">'+esc(P[x].name)+'</button>';}
  function row(k,v){return '<div class="row"><dt>'+k+'</dt><dd>'+v+'</dd></div>';}
  if(p.bornText)rows+=row(p.deceased?'Born':'Born',esc(p.bornText));
  if(p.diedText)rows+=row('Died',esc(p.diedText));
  if(p.dueText)rows+=row('Due',esc(p.dueText));
  if(p.place)rows+=row('Lives',esc(p.place));
  rows+=row('Generation',String(generationOf(id)+1));

  var cur=[],past=[];
  partnerUnions(id).forEach(function(u){
    U[u].partners.forEach(function(x){
      if(x===id)return;
      (U[u].status==='past'?past:cur).push(link(x)+(U[u].label?' <span style="color:var(--ink-3)">('+esc(U[u].label)+')</span>':''));
    });
  });
  var par=parents(id),sib=siblings(id),kd=kids(id);
  var relRows='';
  if(par.length)relRows+=row('Parents',par.map(link).join(' &amp; '));
  if(cur.length)relRows+=row('Partner',cur.join('<br>'));
  if(past.length)relRows+=row('Formerly',past.join('<br>'));
  if(sib.length)relRows+=row('Siblings',sib.map(link).join(', '));
  if(kd.length)relRows+=row('Children',kd.map(link).join(', '));

  drawer.innerHTML=
    '<div class="grip"></div><button class="dclose" aria-label="Close profile">✕</button>'+
    '<div class="dhero">'+
      '<div class="dav'+(p.deceased?' gone':'')+'">'+
        (p.photo?'<img src="'+esc(p.photo)+'" alt="'+esc(p.name)+'">':esc(p.face))+'</div>'+
      '<div><h2>'+esc(p.name)+'</h2>'+
        (p.maiden?'<div class="maiden">née '+esc(p.maiden)+'</div>':'')+
        '<div class="rl">'+esc(p.rel)+'</div>'+
        '<div class="chips">'+
          (p.deceased?'<span class="chip mem">In memory</span>':
            p.expected?'<span class="chip soon">Expected</span>':'<span class="chip">Living</span>')+
          (p.life?'<span class="chip">'+esc(p.life)+'</span>':'')+
        '</div>'+
      '</div>'+
    '</div>'+
    (p.bio||p.note?'<p class="dbio">'+esc(p.bio||p.note)+'</p>':'')+
    '<div class="dsec"><h3>Details</h3><dl class="dl">'+rows+'</dl></div>'+
    (relRows?'<div class="dsec"><h3>Family</h3><dl class="dl">'+relRows+'</dl></div>':'')+
    '<div class="dsec"><h3>Immediate family</h3><div class="minitree">'+miniTree(id)+'</div></div>'+
    '<div class="dact">'+
      '<button class="btn" data-act="center">Center</button>'+
      '<button class="btn" data-act="anc">Ancestors ('+Object.keys(A).length+')</button>'+
      '<button class="btn" data-act="desc">Descendants ('+Object.keys(D).length+')</button>'+
    '</div>';
  drawer.classList.add('on');
  drawer.setAttribute('aria-hidden','false');
  var c=drawer.querySelector('.dclose');if(c)c.focus();
}
function closeProfile(){drawer.classList.remove('on');drawer.setAttribute('aria-hidden','true');}

function miniTree(id){
  var par=parents(id),sp=spouses(id),kd=kids(id);
  var W=300,rowH=52,rows=[par,[id].concat(sp),kd].filter(function(r){return r.length;});
  var H=rows.length*rowH+10,out='';
  var yOf=rows.length===1?[H/2]:rows.map(function(_,i){return 24+i*rowH;});
  rows.forEach(function(r,ri){
    var step=W/(r.length+1);
    r.forEach(function(pid,i){
      var x=step*(i+1),y=yOf[ri];
      if(ri>0){var py=yOf[ri-1];out+='<path class="mt-l" d="M'+x+' '+(y-16)+'C'+x+' '+((y+py)/2)+' '+(W/2)+' '+((y+py)/2)+' '+(W/2)+' '+(py+16)+'"/>';}
      out+='<circle class="mt-c'+(pid===id?' self':'')+'" cx="'+x+'" cy="'+y+'" r="15"/>';
      var nm=P[pid].name.split(' ')[0];
      out+='<text class="mt-n" x="'+x+'" y="'+(y+29)+'">'+esc(nm.length>10?nm.slice(0,9)+'…':nm)+'</text>';
    });
  });
  return '<svg viewBox="0 0 '+W+' '+(H+14)+'" role="img" aria-label="Immediate family diagram">'+out+'</svg>';
}

drawer.addEventListener('click',function(e){
  if(e.target.closest('.dclose'))return closeProfile();
  var g=e.target.closest('[data-goto]');
  if(g){openProfile(g.dataset.goto);return;}
  var a=e.target.closest('[data-act]');
  if(!a)return;
  var id=S.sel;if(!id)return;
  if(a.dataset.act==='center')centerOn(id);
  if(a.dataset.act==='anc')fitTo([id].concat(Object.keys(ancestors(id))),.85);
  if(a.dataset.act==='desc')fitTo([id].concat(Object.keys(descendants(id))),.85);
});

/* ═══════════ search ═══════════ */
var qi=document.getElementById('q'),res=document.getElementById('results'),ri=-1;
function runSearch(){
  var v=qi.value.trim().toLowerCase();res.textContent='';ri=-1;
  if(v.length<1)return;
  var hits=Object.keys(P).filter(function(id){
    var p=P[id];
    return (p.name+' '+(p.maiden||'')+' '+(p.rel||'')).toLowerCase().indexOf(v)>-1;
  }).slice(0,9);
  hits.forEach(function(id){
    var p=P[id],b=document.createElement('button');
    b.innerHTML='<span class="av">'+(p.photo?'<img src="'+esc(p.photo)+'" alt="">':esc(p.face))+'</span>'+
      '<span><span class="nm">'+esc(p.name)+'</span>'+
      (p.life||p.rel?'<br><span class="mt">'+esc(p.rel)+(p.life?' · '+esc(p.life):'')+'</span>':'')+'</span>'+
      '<span class="gen">G'+(generationOf(id)+1)+'</span>';
    b.onclick=function(){
      qi.value='';res.textContent='';
      if(S.view!=='tree')setView('tree');
      select(id,{keep:true});centerOn(id);openProfile(id);
    };
    res.appendChild(b);
  });
}
qi.addEventListener('input',runSearch);
qi.addEventListener('keydown',function(e){
  var items=res.querySelectorAll('button');
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){
    e.preventDefault();if(!items.length)return;
    ri=(ri+(e.key==='ArrowDown'?1:items.length-1))%items.length;
    items.forEach(function(b,i){b.classList.toggle('sel',i===ri);});
    items[ri].scrollIntoView({block:'nearest'});
  }
  if(e.key==='Enter'&&items.length)items[Math.max(0,ri)].click();
  if(e.key==='Escape'){qi.value='';res.textContent='';qi.blur();}
});
document.addEventListener('click',function(e){if(!e.target.closest('.search'))res.textContent='';});

/* ═══════════ timeline ═══════════ */
function buildTimeline(){
  var ev=[];
  Object.keys(P).forEach(function(id){
    var p=P[id];
    if(p.born)ev.push({y:p.born,k:'Born',id:id,t:'b'});
    if(p.died)ev.push({y:p.died,k:'Died',id:id,t:'d'});
    if(p.due)ev.push({y:p.due,k:'Expected',id:id,t:'s'});
  });
  Object.keys(U).forEach(function(uid){
    var u=U[uid];if(!u.date)return;
    u.partners.forEach(function(){});
    ev.push({y:u.date,k:u.label||'Married',id:u.partners[0],t:'m',
      pair:u.partners.map(function(x){return P[x].name;}).join(' & ')});
  });
  ev.sort(function(a,b){return String(a.y).localeCompare(String(b.y));});
  var html='<div class="tlhead"><h2>Family Timeline</h2><p>'+ev.length+
    ' moments across '+G.family+'</p></div><div class="tl">';
  ev.forEach(function(e){
    var p=P[e.id];
    html+='<div class="tlrow"><div class="tlyr">'+esc(String(e.y).split('-')[0])+'</div>'+
      '<span class="tldot '+e.t+'"></span>'+
      '<button class="tlcard" data-goto="'+esc(e.id)+'">'+
        '<span class="av">'+(p.photo?'<img src="'+esc(p.photo)+'" alt="">':esc(p.face))+'</span>'+
        '<span><span class="ev">'+esc(e.k)+'</span><br>'+
        '<span class="who">'+esc(e.pair||p.name)+'</span></span>'+
      '</button></div>';
  });
  document.getElementById('timeline').innerHTML=html+'</div>';
}
document.getElementById('timeline').addEventListener('click',function(e){
  var b=e.target.closest('[data-goto]');if(!b)return;
  setView('tree');select(b.dataset.goto,{keep:true});centerOn(b.dataset.goto);openProfile(b.dataset.goto);
});

/* ═══════════ view switching ═══════════ */
function setView(v){
  S.view=v;
  ['tree','timeline','more'].forEach(function(k){
    var n=document.getElementById(k==='tree'?'stage':k);
    if(k==='tree'){n.style.display=v==='tree'?'':'none';}
    else n.classList.toggle('on',v===k);
  });
  document.querySelectorAll('[data-view]').forEach(function(b){
    b.setAttribute('aria-selected',b.dataset.view===v?'true':'false');});
  document.getElementById('dock').style.display=v==='tree'?'':'none';
  if(v!=='tree')closeProfile();
}
document.querySelectorAll('[data-view]').forEach(function(b){
  b.onclick=function(){setView(b.dataset.view);};});

/* ═══════════ toolbar actions ═══════════ */
function bind(id,fn){var n=document.getElementById(id);if(n)n.onclick=fn;}
bind('zin',function(){var r=stage.getBoundingClientRect();
  zoomAt(r.left+r.width/2,r.top+r.height/2,Math.min(3.2,vk*1.35));});
bind('zout',function(){var r=stage.getBoundingClientRect();
  zoomAt(r.left+r.width/2,r.top+r.height/2,Math.max(.1,vk/1.35));});
bind('fit',function(){fitAll();});
bind('reset',function(){S.sel=null;S.open={};applyEmphasis();closeProfile();homeView();});
bind('me',function(){
  if(!G.me)return;select(G.me,{keep:true});centerOn(G.me);openProfile(G.me);});
bind('focus',function(){
  S.focus=!S.focus;this.setAttribute('aria-pressed',S.focus?'true':'false');
  this.classList.toggle('on',S.focus);
  if(S.focus&&S.sel){
    var set=[S.sel].concat(Object.keys(ancestors(S.sel)),Object.keys(descendants(S.sel)),
      spouses(S.sel),siblings(S.sel));
    fitTo(set,.86);
  }else homeView();
});
bind('colors',function(){
  S.colors=!S.colors;this.setAttribute('aria-pressed',S.colors?'true':'false');
  draw();});
bind('theme',function(){
  var d=document.documentElement;
  var next=d.dataset.theme==='dark'?'light':'dark';
  d.dataset.theme=next;try{localStorage.setItem('mcgee-theme',next);}catch(_){}
  this.textContent=next==='dark'?'☾':'☀';
  this.setAttribute('aria-label',next==='dark'?'Switch to light mode':'Switch to dark mode');});
bind('a11y',function(){
  var open=this.getAttribute('aria-expanded')==='true';
  this.setAttribute('aria-expanded',open?'false':'true');
  document.getElementById('a11ymenu').hidden=open;});
document.getElementById('bigtext').onchange=function(){
  document.body.classList.toggle('text-lg',this.checked);};
document.getElementById('hicon').onchange=function(){
  document.documentElement.dataset.contrast=this.checked?'high':'';};
document.getElementById('nomo').onchange=function(){
  document.documentElement.dataset.motion=this.checked?'off':'';};

document.addEventListener('keydown',function(e){
  if(e.target.matches('input,textarea'))return;
  if(e.key==='Escape'){
    if(drawer.classList.contains('on'))return closeProfile();
    if(S.sel)return select(null);
  }
  if(e.key==='/'){e.preventDefault();qi.focus();}
  if(e.key==='f'||e.key==='F'){fitAll();}
  if(e.key==='m'||e.key==='M'){if(G.me){select(G.me,{keep:true});centerOn(G.me);}}
  if(e.key==='+'||e.key==='='){document.getElementById('zin').click();}
  if(e.key==='-'){document.getElementById('zout').click();}
});

/* ═══════════ boot ═══════════ */
try{var th=localStorage.getItem('mcgee-theme');
  if(th){document.documentElement.dataset.theme=th;
    var tb=document.getElementById('theme');tb.textContent=th==='dark'?'☾':'☀';}
}catch(_){}
if(!G.me){var mb=document.getElementById('me');if(mb)mb.style.display='none';}

layout();draw();buildTimeline();
requestAnimationFrame(function(){homeView(1);});
window.addEventListener('resize',function(){if(S.view==='tree')homeView(260);});
setTimeout(function(){var h=document.getElementById('hint');if(h)h.classList.add('hide');},7000);
})();
"""


# ═══════════════════════════════ page ═══════════════════════════════

NAV = """  <nav class="sr"><a href="index.html">Back to McGee Family home</a></nav>"""


def render_more(d: dict) -> str:
    cards = ""
    for b in d.get("branches", []):
        items = "".join(f"<li>{escape(m)}</li>" for m in b["members"])
        cards += (
            '        <details class="mb">\n'
            f'          <summary><span>{b["emoji"]}</span> {escape(b["title"])} '
            f'<span style="font-weight:400;color:var(--ink-3);font-size:12.5px">'
            f'{len(b["members"])}</span></summary>\n'
            f"          <ul>{items}</ul>\n"
            "        </details>\n"
        )
    q = d.get("open_questions", [])
    qs = ""
    if q:
        qs = ('      <div class="qn"><b>Still to confirm:</b> '
              + " ".join(escape(x) for x in q) + "</div>\n")
    return (
        '  <section id="more">\n    <div class="mwrap">\n'
        '      <div class="tlhead"><h2>More Family</h2>'
        '<p>Relatives we know by name, not yet placed in the tree.</p></div>\n'
        f'      <div class="mgrid">\n{cards}      </div>\n{qs}'
        "    </div>\n  </section>\n"
    )


def build(d: dict) -> str:
    meta = d.get("meta", {})
    data = payload(d)
    data["genNames"] = meta.get("generations", [])
    js_data = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    title = meta.get("title", "Family Tree")
    fam = meta.get("family", "The McGee Family")

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8"/>
<meta name="robots" content="noindex, nofollow"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>
<meta name="description" content="An interactive, living family tree — tap anyone to trace their branch."/>
<title>{escape(title)} · McGee Family</title>
<!-- ══════════════════════════════════════════════════════════════
     GENERATED FILE — DO NOT EDIT BY HAND
     Source:  data/family.json
     Rebuild: double-click "Update Family Tree.command"
     Built:   {date.today().isoformat()}
     ══════════════════════════════════════════════════════════════ -->
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="The McGee Family"/>
<meta property="og:url" content="https://mcgeefamily2025.com/levi-family-tree.html"/>
<meta property="og:title" content="{escape(title)} · McGee Family"/>
<meta property="og:description" content="Trace every branch of the family. Tap anyone to see where they fit."/>
<meta name="theme-color" content="#7A9E7E" media="(prefers-color-scheme: light)"/>
<meta name="theme-color" content="#14110e" media="(prefers-color-scheme: dark)"/>
<link rel="manifest" href="manifest.json"/>
<meta name="mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-title" content="McGee Family"/>
<link rel="icon" type="image/svg+xml" href="favicon.svg"/>
<link rel="canonical" href="https://mcgeefamily2025.com/levi-family-tree.html"/>
<style>{CSS}</style>
</head>
<body class="tree-page">

{NAV}

<header id="bar">
  <div class="brand">
    <h1>{escape(title)}</h1>
    <span class="sub">{escape(fam)}</span>
  </div>

  <div class="search">
    <label class="sr" for="q">Find a family member</label>
    <input type="search" id="q" placeholder="Find someone   /" autocomplete="off"
           role="combobox" aria-expanded="false" aria-controls="results"/>
    <div id="results" class="results" role="listbox" aria-label="Search results"></div>
  </div>

  <span class="grow"></span>

  <div class="seg" role="tablist" aria-label="Choose a view">
    <button class="btn" data-view="tree" role="tab" aria-selected="true">Tree</button>
    <button class="btn" data-view="timeline" role="tab" aria-selected="false">Timeline</button>
    <button class="btn" data-view="more" role="tab" aria-selected="false">More</button>
  </div>

  <button class="btn icon ghost" id="theme" aria-label="Switch to dark mode">☀</button>
  <button class="btn icon ghost" id="a11y" aria-expanded="false" aria-controls="a11ymenu"
          aria-label="Accessibility options">⚙</button>
  <div id="a11ymenu" hidden style="position:fixed;top:56px;right:14px;background:var(--card);
       border:1px solid var(--card-line);border-radius:var(--r-m);padding:14px 16px;
       box-shadow:var(--shadow-2);z-index:80;display:grid;gap:10px;font-size:13.5px">
    <label><input type="checkbox" id="bigtext"/> Larger text</label>
    <label><input type="checkbox" id="hicon"/> High contrast</label>
    <label><input type="checkbox" id="nomo"/> Reduce motion</label>
  </div>
</header>

<div id="crumb" aria-live="polite"></div>

<main id="stage">
  <svg id="tree" role="application"
       aria-label="Interactive family tree. Use arrow keys to move between relatives, Enter to select, i for profile.">
    <defs>
      <filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="0" dy="1.5" stdDeviation="2.4" flood-opacity=".13"/>
      </filter>
    </defs>
    <g id="world">
      <g id="bands"></g>
      <g id="links"></g>
      <g id="nodes"></g>
    </g>
  </svg>
</main>

<section id="timeline" aria-label="Family timeline"></section>
{render_more(d)}
<aside id="drawer" role="complementary" aria-label="Person profile" aria-hidden="true"></aside>

<div id="dock">
  <button class="btn wide" id="focus" aria-pressed="false">Focus mode</button>
  <button class="btn wide" id="colors" aria-pressed="true">Branch colors</button>
  <button class="btn wide" id="me">My family</button>
  <div class="grp">
    <button class="btn" id="zin" aria-label="Zoom in">＋</button>
    <button class="btn" id="zout" aria-label="Zoom out">−</button>
    <button class="btn" id="fit" aria-label="Fit whole tree to screen">⤢</button>
    <button class="btn" id="reset" aria-label="Reset view">⟲</button>
  </div>
</div>

<p id="hint">Click a person to trace their branch · double-click for their profile · scroll to zoom</p>

<script>window.__FAMILY__={js_data};</script>
<script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    check = "--check" in sys.argv
    if not DATA.exists():
        die([f"{DATA.relative_to(ROOT)} not found"])
    try:
        d = json.loads(DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die([f"family.json is not valid JSON — line {e.lineno}, col {e.colno}: {e.msg}"])

    if errs := validate(d):
        die(errs)

    n_ph = sum(1 for p in d["people"].values() if p.get("photo"))
    print(f"\033[1;32m✓ Data valid\033[0m — {len(d['people'])} people, "
          f"{len(d['unions'])} households, {n_ph} photos, root '{d['meta']['root']}'")
    if q := d.get("open_questions"):
        print(f"\033[1;33m⚠ {len(q)} open question(s)\033[0m — shown under More")

    if check:
        print("  (--check: nothing written)")
        return

    OUT.write_text(build(d), encoding="utf-8")
    print(f"\033[1;32m✓ Wrote\033[0m {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
