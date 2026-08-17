#!/usr/bin/env python3
"""
Build levi-family-tree.html from data/family.json.

Tiered card layout (the version that worked), plus the interactions that
earned their keep: tap to trace a lineage, search, profile drawer, dark mode.
No SVG canvas, no pan/zoom, no sweeping connector lines.

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
        y, m, d = (int(x) for x in str(iso).split("-"))
        return f"{MONTHS[m - 1]} {d}, {y}"
    except Exception:
        return str(iso)


def year(iso: str | None) -> str:
    return str(iso).split("-")[0] if iso else ""


def die(errors: list[str]) -> None:
    print("\n\033[1;31m✗ BUILD FAILED\033[0m — fix data/family.json:\n", file=sys.stderr)
    for e in errors:
        print(f"  • {e}", file=sys.stderr)
    print(file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════ validation ═══════════════════════════

def validate(d: dict) -> list[str]:
    errors: list[str] = []
    people: dict = d.get("people", {})
    unions: list = d.get("unions", [])
    tiers: list = d.get("tiers", [])
    ids = set(people)

    if not ids:
        return ["'people' is empty."]
    if not tiers:
        return ["'tiers' is empty — nothing would render."]

    for pid, p in people.items():
        if not str(p.get("name", "")).strip():
            errors.append(f"person '{pid}' has no name")
        photo = p.get("photo")
        if photo:
            if not (ROOT / photo).is_file():
                errors.append(f"'{pid}' photo not found: {photo}")
            elif photo != photo.lower():
                errors.append(
                    f"'{pid}' photo has uppercase characters — GitHub Pages is "
                    f"case-sensitive. Rename to lowercase: {photo}")

    seen: set[str] = set()
    for i, u in enumerate(unions):
        uid = u.get("id")
        if not uid:
            errors.append(f"unions[{i}] has no 'id'")
        elif uid in seen:
            errors.append(f"duplicate union id '{uid}'")
        else:
            seen.add(uid)
        if len(u.get("partners", [])) > 2:
            errors.append(f"union '{uid}' has more than 2 partners")
        for key in ("partners", "children", "pets"):
            for ref in u.get(key, []):
                if ref not in ids:
                    errors.append(f"union '{uid}' {key} references unknown '{ref}'")

    # tiers: every person placed, each exactly once
    placed: list[str] = []
    for t in tiers:
        for row in t.get("rows", []):
            for pid in (row if isinstance(row, list) else [row]):
                if pid not in ids:
                    errors.append(f"tier '{t.get('title')}' references unknown '{pid}'")
                else:
                    placed.append(pid)
    # A person may legitimately appear twice only if they head two households
    # (e.g. Jennifer with Jim and with Jeff). Flag anything beyond that.
    heads = {}
    for u in unions:
        for pid in u.get("partners", []):
            heads[pid] = heads.get(pid, 0) + 1
    for pid in set(placed):
        n = placed.count(pid)
        if n > max(1, heads.get(pid, 1)):
            errors.append(f"'{pid}' appears {n}× in tiers but heads only "
                          f"{heads.get(pid,0)} household(s)")
    for pid in sorted(ids - set(placed)):
        errors.append(f"'{pid}' ({people[pid].get('name')}) is not placed in any tier")

    me = d.get("meta", {}).get("me")
    if me and me not in ids:
        errors.append(f"meta.me '{me}' is not a known person")

    return errors


# ═══════════════════════════ payload ═══════════════════════════

def payload(d: dict) -> dict:
    people, unions = d["people"], d["unions"]
    out_people = {}
    for pid, p in people.items():
        e = {"name": p["name"], "rel": p.get("rel", ""), "face": p.get("face", "👤")}
        for k in ("photo", "note", "badge", "style"):
            if p.get(k):
                e[k] = p[k]
        if p.get("born"):
            e["bornText"] = pretty(p["born"])
        if p.get("died"):
            e["diedText"] = pretty(p["died"])
        if p.get("due"):
            e["dueText"] = pretty(p["due"])
        e["deceased"] = bool(p.get("died"))
        ys, yd = year(p.get("born")), year(p.get("died"))
        if ys and yd:
            e["life"] = f"{ys}–{yd}"
        elif ys:
            e["life"] = f"b. {ys}"
        elif p.get("due"):
            e["life"] = "due " + pretty(p["due"])
        out_people[pid] = e

    out_unions, own, birth = {}, {}, {}
    for u in unions:
        out_unions[u["id"]] = {
            "partners": u.get("partners", []),
            "children": u.get("children", []),
            "pets": u.get("pets", []),
            "label": u.get("label", ""),
            "status": u.get("status", ""),
        }
        for pid in u.get("partners", []):
            own.setdefault(pid, []).append(u["id"])
        for cid in u.get("children", []):
            birth[cid] = u["id"]

    return {"people": out_people, "unions": out_unions, "own": own,
            "birth": birth, "me": d.get("meta", {}).get("me", "")}


# ═══════════════════════════ CSS ═══════════════════════════

CSS = r"""
:root{
  --sage:#7a9e7e; --sage-light:#b2cdb5; --sage-pale:#eaf2eb;
  --cream:#faf6ef; --cream-dark:#f0e9dc;
  --brown:#6b4f3a; --brown-light:#a0785a; --brown-pale:#ede0d4;
  --terracotta:#c4714a; --terra-pale:#f5e4d8;
  --mushroom:#8e7b6a; --forest:#3d6b52;
  --ink:#2c2114; --ink-2:#5a4a3a; --ink-3:#8e7b6a;
  --card:#fff; --line:rgba(107,79,58,.16);
  --sh-1:0 1px 3px rgba(60,40,20,.06),0 2px 8px rgba(60,40,20,.04);
  --sh-2:0 8px 24px rgba(60,40,20,.12);
  --glass:rgba(250,246,239,.85);
  --r-s:10px; --r-m:16px; --r-l:22px; --r-f:999px;
  --ease:cubic-bezier(.22,.9,.3,1);
}
html[data-theme=dark]{
  --sage:#6f9c7d; --sage-light:#3f6d54; --sage-pale:#1e2a22;
  --cream:#15120f; --cream-dark:#1d1916;
  --brown:#c8a888; --brown-light:#a88a6c; --brown-pale:#241e19;
  --terracotta:#e08b60; --terra-pale:#2a1f18;
  --mushroom:#9a8c7c; --forest:#8fc9a5;
  --ink:#f4efe7; --ink-2:#cabfb2; --ink-3:#948a7d;
  --card:#211c18; --line:rgba(244,239,231,.13);
  --sh-1:0 1px 3px rgba(0,0,0,.4); --sh-2:0 8px 24px rgba(0,0,0,.55);
  --glass:rgba(21,18,15,.86);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body.tree{
  background:var(--cream); color:var(--ink); min-height:100svh;
  font:400 15px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",sans-serif;
  -webkit-font-smoothing:antialiased;
  transition:background .35s var(--ease),color .35s var(--ease);
}
html[data-contrast=high]{--line:rgba(107,79,58,.45);--ink-2:#3b2f22;--ink-3:#5a4a3a}
body.tree.big{font-size:17px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
:focus-visible{outline:3px solid var(--sage);outline-offset:3px;border-radius:6px}
@media(prefers-reduced-motion:reduce){*{animation-duration:.001s!important;transition-duration:.001s!important}}
html[data-motion=off] *{animation:none!important;transition:none!important}

/* ── header ─────────────────────────────────────────────── */
.top{
  position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:12px;
  padding:13px 20px;background:var(--glass);
  -webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid var(--line);
}
.top .brand{display:flex;align-items:baseline;gap:9px;min-width:0}
.top h1{font:700 18px/1.1 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.022em;white-space:nowrap}
.top .tag{font-size:11.5px;color:var(--ink-3);white-space:nowrap}
@media(max-width:700px){.top .tag{display:none}}
.spacer{flex:1 1 auto;min-width:6px}
.btn{
  font:inherit;font-size:13px;font-weight:600;color:var(--ink-2);
  background:color-mix(in srgb,var(--ink) 7%,transparent);border:none;
  border-radius:var(--r-f);padding:8px 14px;cursor:pointer;white-space:nowrap;
  transition:background .2s,color .2s,transform .12s;
}
.btn:hover{background:color-mix(in srgb,var(--ink) 13%,transparent)}
.btn:active{transform:scale(.96)}
.btn.on{background:var(--forest);color:var(--cream)}
.btn.icon{width:34px;height:34px;padding:0;display:grid;place-items:center;font-size:15px;background:none}
.search{position:relative}
.search input{
  font:inherit;font-size:13.5px;color:var(--ink);background:var(--card);
  border:1px solid var(--line);border-radius:var(--r-f);
  padding:8px 14px 8px 33px;width:200px;transition:width .28s var(--ease);
}
.search input:focus{width:250px}
.search::before{content:"⌕";position:absolute;left:12px;top:50%;transform:translateY(-52%);
  font-size:16px;color:var(--ink-3);pointer-events:none}
@media(max-width:620px){.search input{width:120px}.search input:focus{width:160px}}
.results{position:absolute;top:calc(100% + 8px);left:0;min-width:280px;max-height:320px;
  overflow-y:auto;background:var(--card);border:1px solid var(--line);
  border-radius:var(--r-m);box-shadow:var(--sh-2);z-index:60;padding:5px}
.results:empty{display:none}
.results button{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
  font:inherit;font-size:13.5px;background:none;border:none;padding:8px 10px;
  border-radius:var(--r-s);cursor:pointer;color:var(--ink)}
.results button:hover,.results button.sel{background:var(--sage-pale)}
.results .av{width:32px;height:32px;border-radius:var(--r-f);overflow:hidden;flex:0 0 32px;
  background:var(--sage-pale);display:grid;place-items:center;font-size:16px}
.results .av img{width:100%;height:100%;object-fit:cover}
.results .mt{font-size:11.5px;color:var(--ink-3)}

/* ── hero ───────────────────────────────────────────────── */
.hero{
  background:linear-gradient(165deg,var(--sage-pale) 0%,var(--cream) 58%,var(--brown-pale) 100%);
  padding:52px 24px 40px;text-align:center;
}
.hero p{font-size:16.5px;color:var(--ink-2);max-width:460px;margin:0 auto}
.bar{display:flex;flex-wrap:wrap;gap:9px;justify-content:center;margin-top:22px}

/* ── tiers ──────────────────────────────────────────────── */
.wrap{max-width:1180px;margin:0 auto;padding:34px 20px 80px}
.tier{margin-bottom:6px;padding-top:26px}
.tier-h{display:flex;align-items:center;gap:12px;font-size:12px;font-weight:600;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-bottom:20px}
.tier-h::after{content:"";flex:1;height:1px;
  background:linear-gradient(90deg,var(--sage-light),transparent)}
.row{display:flex;flex-wrap:wrap;gap:18px 22px;justify-content:center}
.link{width:2px;height:26px;margin:0 auto;border-radius:2px;
  background:linear-gradient(180deg,var(--sage-light),color-mix(in srgb,var(--sage-light) 25%,transparent))}

/* couple pod */
.pod{position:relative;display:flex;background:color-mix(in srgb,var(--card) 55%,transparent);
  border:1px solid var(--line);border-radius:var(--r-l);padding:13px 15px 19px}
.pod::before{content:"";position:absolute;top:44px;left:50%;width:20px;height:2px;
  margin-left:-10px;background:var(--sage-light);border-radius:2px}
.pod.solo::before{display:none}
.pod .p+.p{margin-left:20px}
.pod-l{position:absolute;left:50%;bottom:5px;transform:translateX(-50%);font-size:10px;
  font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);white-space:nowrap}
.pod.past{border-style:dashed;border-color:color-mix(in srgb,var(--mushroom) 45%,transparent);
  background:color-mix(in srgb,var(--card) 32%,transparent)}
.pod.past::before{background:none;border-top:2px dashed var(--mushroom);height:0}
.pod.past .pod-l{font-style:italic;color:var(--mushroom)}

/* person card */
.p{
  width:132px;flex-shrink:0;background:var(--card);border:1px solid var(--line);
  border-radius:var(--r-m);padding:15px 11px 13px;text-align:center;cursor:pointer;
  box-shadow:var(--sh-1);font:inherit;color:inherit;
  transition:transform .22s var(--ease),box-shadow .22s,border-color .22s,opacity .3s;
}
.p:hover{transform:translateY(-3px);box-shadow:var(--sh-2);border-color:var(--sage)}
.p:active{transform:translateY(-1px) scale(.985)}
.av{position:relative;width:60px;height:60px;margin:0 auto 10px}
.av-in{width:100%;height:100%;border-radius:var(--r-f);overflow:hidden;background:var(--sage-pale);
  display:grid;place-items:center;font-size:28px;border:2.5px solid color-mix(in srgb,var(--sage) 32%,transparent)}
.av-in img{width:100%;height:100%;object-fit:cover;display:block}
.nm{font-size:14px;font-weight:700;line-height:1.24;letter-spacing:-.015em}
.rl{font-size:10.5px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;
  color:var(--sage);margin-top:4px}
.lf{font-size:11px;color:var(--ink-3);margin-top:3px;font-variant-numeric:tabular-nums}
.pip{position:absolute;right:1px;bottom:1px;width:12px;height:12px;border-radius:var(--r-f);
  background:var(--sage);border:2.5px solid var(--card)}
.pip.gone{background:var(--ink-3)}
.badge{position:absolute;top:-7px;left:50%;transform:translateX(-50%);background:var(--sage);
  color:#fff;font-size:8.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  padding:3px 8px;border-radius:var(--r-f);white-space:nowrap;box-shadow:var(--sh-1)}

.p.is-levi{border:2px solid var(--terracotta);background:linear-gradient(165deg,var(--card),var(--terra-pale))}
.p.is-levi .rl{color:var(--terracotta)}
.p.is-baby{border:2px dashed var(--sage);background:linear-gradient(165deg,var(--card),var(--sage-pale))}
.p.is-pet .rl{color:var(--brown-light)}
.p.is-memory{background:var(--cream-dark)}
.p.is-memory .av-in img{filter:grayscale(.9);opacity:.85}
.p.is-memory .rl{color:var(--mushroom)}

/* highlight states */
.p.dim{opacity:.26}
.p.sel{border-color:var(--terracotta);border-width:2px;box-shadow:0 0 0 4px color-mix(in srgb,var(--terracotta) 16%,transparent),var(--sh-2)}
.p.line{border-color:var(--forest);box-shadow:0 0 0 3px color-mix(in srgb,var(--forest) 13%,transparent)}
.p.kin{border-color:var(--sage)}
.pod.dim{opacity:.26}

/* ── banner ─────────────────────────────────────────────── */
.note{position:sticky;top:60px;z-index:40;max-width:1180px;margin:0 auto;
  padding:0 20px;pointer-events:none}
.note-in{display:flex;align-items:center;gap:10px;background:var(--card);
  border:1px solid var(--line);border-left:3px solid var(--terracotta);
  border-radius:var(--r-m);padding:10px 14px;box-shadow:var(--sh-1);font-size:13.5px;
  color:var(--ink-2);pointer-events:auto;margin-top:12px}
.note-in b{color:var(--ink)}
.note-in button{margin-left:auto;background:none;border:none;cursor:pointer;
  color:var(--ink-3);font-size:15px;padding:0 3px}
.note[hidden]{display:none}

/* ── drawer ─────────────────────────────────────────────── */
#dr{position:fixed;top:0;right:0;bottom:0;width:372px;z-index:70;background:var(--glass);
  -webkit-backdrop-filter:saturate(180%) blur(24px);backdrop-filter:saturate(180%) blur(24px);
  border-left:1px solid var(--line);box-shadow:-12px 0 40px rgba(60,40,20,.12);
  transform:translateX(101%);transition:transform .4s var(--ease);
  overflow-y:auto;overscroll-behavior:contain;padding:24px 22px 44px}
#dr.on{transform:none}
@media(max-width:760px){
  #dr{top:auto;left:0;width:auto;max-height:84vh;border-left:none;border-top:1px solid var(--line);
    border-radius:var(--r-l) var(--r-l) 0 0;transform:translateY(101%);
    padding-bottom:calc(44px + env(safe-area-inset-bottom));box-shadow:0 -12px 40px rgba(0,0,0,.22)}
}
.grip{width:38px;height:4px;border-radius:2px;background:var(--line);margin:0 auto 16px;display:none}
@media(max-width:760px){.grip{display:block}}
.dx{position:absolute;top:18px;right:18px;width:30px;height:30px;border-radius:var(--r-f);
  border:none;background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--ink-2);
  cursor:pointer;font-size:14px}
.dhead{display:flex;gap:14px;align-items:flex-start;margin:0 34px 18px 0}
.dav{width:74px;height:74px;border-radius:var(--r-m);overflow:hidden;flex:0 0 74px;
  background:var(--sage-pale);display:grid;place-items:center;font-size:33px;box-shadow:var(--sh-1)}
.dav img{width:100%;height:100%;object-fit:cover}
.dav.gone img{filter:grayscale(.9)}
.dhead h2{font:700 21px/1.16 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.022em}
.dhead .rl{margin-top:5px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip{font-size:11px;font-weight:600;padding:4px 9px;border-radius:var(--r-f);
  background:color-mix(in srgb,var(--sage) 17%,transparent);color:var(--ink-2)}
.chip.mem{background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--ink-3)}
.chip.soon{background:color-mix(in srgb,var(--terracotta) 18%,transparent);color:var(--terracotta)}
.dbio{font-size:14px;line-height:1.62;color:var(--ink-2);margin-bottom:18px}
.dsec{margin-bottom:18px}
.dsec h3{font:600 10.5px -apple-system,sans-serif;color:var(--ink-3);letter-spacing:.12em;
  text-transform:uppercase;margin-bottom:9px;display:flex;align-items:center;gap:8px}
.dsec h3::after{content:"";flex:1;height:1px;background:var(--line)}
.dl{display:grid;gap:8px}
.dl .r{display:flex;gap:10px;font-size:13.5px;align-items:baseline}
.dl dt{flex:0 0 84px;color:var(--ink-3);font-weight:600;font-size:12px}
.dl dd{margin:0;color:var(--ink-2)}
.lnk{font:inherit;font-size:13.5px;color:var(--forest);background:none;border:none;padding:0;
  cursor:pointer;text-decoration:underline;
  text-decoration-color:color-mix(in srgb,var(--forest) 35%,transparent);text-underline-offset:2px}
.lnk:hover{text-decoration-color:var(--forest)}
.dbtn{width:100%;margin-top:4px}

/* ── more family ────────────────────────────────────────── */
.more{max-width:900px;margin:0 auto;padding:0 20px 70px}
.more-h{text-align:center;font-size:12px;font-weight:600;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);margin-bottom:20px}
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:14px}
.mb{background:var(--card);border:1px solid var(--line);border-radius:var(--r-l);overflow:hidden}
.mb summary{cursor:pointer;list-style:none;padding:16px 19px;display:flex;align-items:center;
  gap:11px;font:700 15.5px -apple-system,sans-serif;color:var(--forest);letter-spacing:-.015em}
.mb summary::-webkit-details-marker{display:none}
.mb summary::after{content:"＋";margin-left:auto;color:var(--ink-3);transition:transform .25s}
.mb[open] summary::after{transform:rotate(45deg)}
.mb ul{list-style:none;display:flex;flex-wrap:wrap;gap:6px;padding:0 19px 19px}
.mb li{background:var(--sage-pale);color:var(--ink-2);border-radius:var(--r-f);
  padding:5px 12px;font-size:13px}

.foot{text-align:center;padding:34px 20px 46px;border-top:1px solid var(--line);
  background:var(--brown-pale)}
.foot .t{font:700 18px -apple-system,"SF Pro Display",sans-serif;color:var(--brown);letter-spacing:-.02em}
.foot .s{font-size:12.5px;color:var(--ink-3);margin-top:6px}

@media(max-width:640px){
  .p{width:calc(50% - 11px);min-width:126px}
  .pod{width:100%;padding:11px 12px 19px}
  .pod .p+.p{margin-left:11px}
  .row{gap:14px}
  .hero{padding:38px 20px 30px}
}
"""


# ═══════════════════════════ JS ═══════════════════════════

JS = r"""
(function(){
'use strict';
var G=window.__FAM__,P=G.people,U=G.unions,OWN=G.own,BIRTH=G.birth;
var sel=null;

function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function q(s,r){return (r||document).querySelector(s);}
function qa(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s));}

/* ── relationships ── */
function spouses(id){var o=[];(OWN[id]||[]).forEach(function(u){
  U[u].partners.forEach(function(x){if(x!==id&&o.indexOf(x)<0)o.push(x);});});return o;}
function kids(id){var o=[];(OWN[id]||[]).forEach(function(u){
  (U[u].children||[]).forEach(function(c){if(o.indexOf(c)<0)o.push(c);});});return o;}
function parents(id){var b=BIRTH[id];return b?U[b].partners.slice():[];}
function siblings(id){var b=BIRTH[id];return b?(U[b].children||[]).filter(function(c){
  return c!==id;}):[];}
function ancestors(id){var o={},qq=parents(id);
  while(qq.length){var x=qq.pop();if(o[x])continue;o[x]=1;parents(x).forEach(function(p){qq.push(p);});}
  return o;}
function descendants(id){var o={},qq=kids(id);
  while(qq.length){var x=qq.pop();if(o[x])continue;o[x]=1;kids(x).forEach(function(c){qq.push(c);});}
  return o;}

/* ── highlight ── */
function highlight(id){
  var note=q('#note');
  if(!id){
    qa('.p').forEach(function(n){n.classList.remove('dim','sel','line','kin');});
    qa('.pod').forEach(function(n){n.classList.remove('dim');});
    note.hidden=true;return;
  }
  var A=ancestors(id),D=descendants(id),kin={};
  spouses(id).forEach(function(x){kin[x]=1;});
  siblings(id).forEach(function(x){kin[x]=1;});
  var keep={};keep[id]=1;
  Object.keys(A).forEach(function(k){keep[k]=1;spouses(k).forEach(function(s){keep[s]=1;});});
  Object.keys(D).forEach(function(k){keep[k]=1;spouses(k).forEach(function(s){keep[s]=1;});});
  Object.keys(kin).forEach(function(k){keep[k]=1;});

  qa('.p').forEach(function(n){
    var i=n.dataset.id;
    n.classList.toggle('sel',i===id);
    n.classList.toggle('line',!!(A[i]||D[i]));
    n.classList.toggle('kin',!!kin[i]&&i!==id);
    n.classList.toggle('dim',!keep[i]);
  });
  qa('.pod').forEach(function(pod){
    var any=qa('.p',pod).some(function(n){return keep[n.dataset.id];});
    pod.classList.toggle('dim',!any);
  });

  var p=P[id],na=Object.keys(A).length,nd=Object.keys(D).length;
  q('#note-t').innerHTML='Showing <b>'+esc(p.name)+"</b>'s family · "+
    na+' above · '+nd+' below';
  note.hidden=false;
}

function select(id){
  if(sel===id){sel=null;highlight(null);return;}
  sel=id;highlight(id);
}

/* ── drawer ── */
var dr=q('#dr');
function open(id){
  var p=P[id];if(!p)return;
  sel=id;highlight(id);
  function L(x){return '<button class="lnk" data-go="'+esc(x)+'">'+esc(P[x].name)+'</button>';}
  function R(k,v){return '<div class="r"><dt>'+k+'</dt><dd>'+v+'</dd></div>';}
  var det='';
  if(p.bornText)det+=R('Born',esc(p.bornText));
  if(p.diedText)det+=R('Died',esc(p.diedText));
  if(p.dueText)det+=R('Due',esc(p.dueText));

  var cur=[],past=[];
  (OWN[id]||[]).forEach(function(u){
    U[u].partners.forEach(function(x){
      if(x!==id)(U[u].status==='past'?past:cur).push(L(x));});
  });
  var fam='';
  var pa=parents(id),sb=siblings(id),kd=kids(id);
  if(pa.length)fam+=R('Parents',pa.map(L).join(' &amp; '));
  if(cur.length)fam+=R('Partner',cur.join(', '));
  if(past.length)fam+=R('Formerly',past.join(', '));
  if(sb.length)fam+=R('Siblings',sb.map(L).join(', '));
  if(kd.length)fam+=R('Children',kd.map(L).join(', '));

  dr.innerHTML='<div class="grip"></div><button class="dx" aria-label="Close">✕</button>'+
    '<div class="dhead"><div class="dav'+(p.deceased?' gone':'')+'">'+
      (p.photo?'<img src="'+esc(p.photo)+'" alt="'+esc(p.name)+'">':esc(p.face))+'</div>'+
      '<div><h2>'+esc(p.name)+'</h2><div class="rl">'+esc(p.rel)+'</div>'+
      '<div class="chips">'+
        (p.deceased?'<span class="chip mem">In memory</span>':
          p.dueText?'<span class="chip soon">Coming soon</span>':'<span class="chip">Living</span>')+
        (p.life?'<span class="chip">'+esc(p.life)+'</span>':'')+
      '</div></div></div>'+
    (p.note?'<p class="dbio">'+esc(p.note)+'</p>':'')+
    (det?'<div class="dsec"><h3>Dates</h3><dl class="dl">'+det+'</dl></div>':'')+
    (fam?'<div class="dsec"><h3>Family</h3><dl class="dl">'+fam+'</dl></div>':'')+
    '<button class="btn dbtn" data-scroll="'+esc(id)+'">Find on the page</button>';
  dr.classList.add('on');dr.setAttribute('aria-hidden','false');
  var x=q('.dx',dr);if(x)x.focus();
}
function close(){dr.classList.remove('on');dr.setAttribute('aria-hidden','true');}

dr.addEventListener('click',function(e){
  if(e.target.closest('.dx'))return close();
  var g=e.target.closest('[data-go]');if(g)return open(g.dataset.go);
  var s=e.target.closest('[data-scroll]');
  if(s){scrollTo_(s.dataset.scroll);close();}
});
function scrollTo_(id){
  var n=q('.p[data-id="'+id+'"]');if(!n)return;
  n.scrollIntoView({behavior:'smooth',block:'center'});
  n.animate?n.animate([{transform:'scale(1)'},{transform:'scale(1.07)'},{transform:'scale(1)'}],
    {duration:620,easing:'cubic-bezier(.22,.9,.3,1)'}):0;
}

/* ── card clicks ── */
document.addEventListener('click',function(e){
  var card=e.target.closest('.p');
  if(card){
    var id=card.dataset.id;
    if(e.detail>1||e.altKey)open(id); else select(id);
    return;
  }
  if(!e.target.closest('#dr,.search,.top'))
    if(!e.target.closest('.note-in'))return;
});
document.addEventListener('dblclick',function(e){
  var card=e.target.closest('.p');if(card)open(card.dataset.id);});
document.addEventListener('keydown',function(e){
  if(e.target.matches('input'))return;
  if(e.key==='Escape'){if(dr.classList.contains('on'))return close();if(sel)return select(sel);}
  if(e.key==='/'){e.preventDefault();q('#q').focus();}
});
qa('.p').forEach(function(n){
  n.addEventListener('keydown',function(e){
    if(e.key==='Enter'||e.key===' '){e.preventDefault();select(n.dataset.id);}
    if(e.key==='i'||e.key==='I'){e.preventDefault();open(n.dataset.id);}
  });
});

/* ── controls ── */
q('#note-x').onclick=function(){select(sel);};
q('#me').onclick=function(){if(G.me){open(G.me);scrollTo_(G.me);}};
q('#all').onclick=function(){sel=null;highlight(null);
  window.scrollTo({top:0,behavior:'smooth'});};
q('#theme').onclick=function(){
  var d=document.documentElement,n=d.dataset.theme==='dark'?'light':'dark';
  d.dataset.theme=n;this.textContent=n==='dark'?'☾':'☀';
  try{localStorage.setItem('mcgee-theme',n);}catch(_){}};
q('#gear').onclick=function(){
  var m=q('#opts'),o=m.hidden;m.hidden=!o;this.setAttribute('aria-expanded',o?'true':'false');};
q('#big').onchange=function(){document.body.classList.toggle('big',this.checked);};
q('#hc').onchange=function(){document.documentElement.dataset.contrast=this.checked?'high':'';};
q('#rm').onchange=function(){document.documentElement.dataset.motion=this.checked?'off':'';};

/* ── search ── */
var qi=q('#q'),res=q('#results'),ri=-1;
qi.addEventListener('input',function(){
  var v=qi.value.trim().toLowerCase();res.innerHTML='';ri=-1;
  if(!v)return;
  Object.keys(P).filter(function(id){
    return (P[id].name+' '+P[id].rel).toLowerCase().indexOf(v)>-1;}).slice(0,8)
  .forEach(function(id){
    var p=P[id],b=document.createElement('button');
    b.innerHTML='<span class="av">'+(p.photo?'<img src="'+esc(p.photo)+'" alt="">':esc(p.face))+
      '</span><span><b>'+esc(p.name)+'</b><br><span class="mt">'+esc(p.rel)+
      (p.life?' · '+esc(p.life):'')+'</span></span>';
    b.onclick=function(){qi.value='';res.innerHTML='';open(id);scrollTo_(id);};
    res.appendChild(b);
  });
});
qi.addEventListener('keydown',function(e){
  var it=qa('button',res);
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!it.length)return;
    ri=(ri+(e.key==='ArrowDown'?1:it.length-1))%it.length;
    it.forEach(function(b,i){b.classList.toggle('sel',i===ri);});it[ri].scrollIntoView({block:'nearest'});}
  if(e.key==='Enter'&&it.length)it[Math.max(0,ri)].click();
  if(e.key==='Escape'){qi.value='';res.innerHTML='';qi.blur();}
});
document.addEventListener('click',function(e){if(!e.target.closest('.search'))res.innerHTML='';});

/* ── boot ── */
try{var t=localStorage.getItem('mcgee-theme');
  if(t){document.documentElement.dataset.theme=t;q('#theme').textContent=t==='dark'?'☾':'☀';}
}catch(_){}
if(!G.me)q('#me').style.display='none';
})();
"""


# ═══════════════════════════ render ═══════════════════════════

def card(pid: str, p: dict) -> str:
    cls = "p" + "".join(f" is-{s}" for s in str(p.get("style", "")).split() if s)
    ys, yd = year(p.get("born")), year(p.get("died"))
    if ys and yd:
        life = f"{ys}–{yd}"
    elif ys:
        life = f"b. {ys}"
    elif p.get("due"):
        life = "due " + pretty(p["due"])
    else:
        life = ""
    inner = (f'<img src="{escape(p["photo"])}" alt="{escape(p["name"])}" '
             f'loading="lazy" decoding="async" width="60" height="60">'
             if p.get("photo") else escape(p.get("face", "👤")))
    gone = " gone" if p.get("died") else ""
    badge = (f'<span class="badge">{escape(p["badge"])}</span>'
             if p.get("badge") else "")
    return (
        f'<button class="{cls}" data-id="{escape(pid)}" '
        f'aria-label="{escape(p["name"])}, {escape(p.get("rel",""))}">'
        f'<span class="av"><span class="av-in">{inner}</span>'
        f'<span class="pip{gone}"></span>{badge}</span>'
        f'<span class="nm">{escape(p["name"])}</span>'
        f'<span class="rl">{escape(p.get("rel",""))}</span>'
        + (f'<span class="lf">{life}</span>' if life else "")
        + "</button>"
    )


def union_for(d: dict, pair: list[str]) -> dict | None:
    want = set(pair)
    for u in d.get("unions", []):
        if set(u.get("partners", [])) == want:
            return u
    return None


def render_tiers(d: dict) -> str:
    people = d["people"]
    out = []
    for i, t in enumerate(d["tiers"]):
        rows = []
        for row in t["rows"]:
            if isinstance(row, list):
                u = union_for(d, row)
                cards = "".join(card(x, people[x]) for x in row)
                lbl = (f'<span class="pod-l">{escape(u["label"])}</span>'
                       if u and u.get("label") else "")
                past = " past" if u and u.get("status") == "past" else ""
                solo = " solo" if len(row) == 1 else ""
                rows.append(f'          <div class="pod{past}{solo}">{cards}{lbl}</div>')
            else:
                rows.append("          " + card(row, people[row]))
        link = '        <div class="link" aria-hidden="true"></div>\n' if i else ""
        out.append(
            link
            + '        <section class="tier">\n'
            f'          <h2 class="tier-h">{escape(t["title"])}</h2>\n'
            '          <div class="row">\n' + "\n".join(rows) + "\n"
            "          </div>\n"
            "        </section>\n"
        )
    return "".join(out)


def render_more(d: dict) -> str:
    if not d.get("branches"):
        return ""
    cards = ""
    for b in d["branches"]:
        items = "".join(f"<li>{escape(m)}</li>" for m in b["members"])
        cards += (
            '        <details class="mb">\n'
            f'          <summary><span>{b["emoji"]}</span> {escape(b["title"])}</summary>\n'
            f"          <ul>{items}</ul>\n        </details>\n"
        )
    return ('  <section class="more">\n    <p class="more-h">The Wider Family</p>\n'
            f'    <div class="mgrid">\n{cards}    </div>\n  </section>\n')


NAV = """  <nav class="sr"><a href="index.html">McGee Family home</a></nav>"""


def build(d: dict) -> str:
    m = d.get("meta", {})
    js = json.dumps(payload(d), ensure_ascii=False, separators=(",", ":"))
    title = m.get("title", "Family Tree")
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8"/>
<meta name="robots" content="noindex, nofollow"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>
<meta name="description" content="Levi's immediate family — parents, aunts, uncles, and cousins."/>
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
<meta property="og:description" content="Tap anyone to see how they connect."/>
<meta name="theme-color" content="#7A9E7E"/>
<link rel="manifest" href="manifest.json"/>
<meta name="mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-title" content="McGee Family"/>
<link rel="icon" type="image/svg+xml" href="favicon.svg"/>
<link rel="canonical" href="https://mcgeefamily2025.com/levi-family-tree.html"/>
<style>{CSS}</style>
</head>
<body class="tree">

{NAV}

<header class="top">
  <div class="brand">
    <h1>{escape(title)}</h1>
    <span class="tag">{escape(m.get('family',''))}</span>
  </div>
  <div class="search">
    <label class="sr" for="q">Find a family member</label>
    <input type="search" id="q" placeholder="Find someone   /" autocomplete="off"/>
    <div id="results" class="results" role="listbox"></div>
  </div>
  <span class="spacer"></span>
  <button class="btn" id="me">My family</button>
  <button class="btn" id="all">Show everyone</button>
  <button class="btn icon" id="theme" aria-label="Toggle dark mode">☀</button>
  <button class="btn icon" id="gear" aria-expanded="false" aria-controls="opts"
          aria-label="Display options">⚙</button>
  <div id="opts" hidden style="position:absolute;top:52px;right:16px;background:var(--card);
       border:1px solid var(--line);border-radius:var(--r-m);padding:14px 16px;
       box-shadow:var(--sh-2);z-index:80;display:grid;gap:10px;font-size:13.5px">
    <label><input type="checkbox" id="big"/> Larger text</label>
    <label><input type="checkbox" id="hc"/> High contrast</label>
    <label><input type="checkbox" id="rm"/> Reduce motion</label>
  </div>
</header>

<div class="note" id="note" hidden>
  <div class="note-in">
    <span id="note-t"></span>
    <button id="note-x" aria-label="Show everyone again">✕</button>
  </div>
</div>

<header class="hero">
  <p>{escape(m.get('intro',''))}</p>
  <div class="bar">
    <span class="chip">Tap a card to trace their family</span>
    <span class="chip">Double-tap for their story</span>
  </div>
</header>

<main class="wrap">
{render_tiers(d)}</main>

{render_more(d)}

<aside id="dr" role="complementary" aria-label="Person details" aria-hidden="true"></aside>

<footer class="foot">
  <p class="t">Faith. Family. Forever.</p>
  <p class="s">The McGee Family · Queen Creek, Arizona</p>
</footer>

<script>window.__FAM__={js};</script>
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
          f"{len(d['unions'])} households, {len(d['tiers'])} tiers, {n_ph} photos")

    if check:
        print("  (--check: nothing written)")
        return

    OUT.write_text(build(d), encoding="utf-8")
    print(f"\033[1;32m✓ Wrote\033[0m {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
