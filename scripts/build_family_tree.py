#!/usr/bin/env python3
"""
Build levi-family-tree.html from data/family.json.

An interactive, expandable family tree rooted on one household.
Tap a person -> their own household expands in place.

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

    seen_uids: set[str] = set()
    for i, u in enumerate(unions):
        uid = u.get("id")
        if not uid:
            errors.append(f"unions[{i}] has no 'id'")
        elif uid in seen_uids:
            errors.append(f"duplicate union id '{uid}'")
        else:
            seen_uids.add(uid)

        parts = u.get("partners", [])
        if not parts:
            errors.append(f"union '{uid}' has no partners")
        if len(parts) > 2:
            errors.append(f"union '{uid}' has {len(parts)} partners — max 2")
        for pid in parts:
            if pid not in ids:
                errors.append(f"union '{uid}' partner '{pid}' not in people")
        for cid in u.get("children", []):
            if cid not in ids:
                errors.append(f"union '{uid}' child '{cid}' not in people")
        for pet in u.get("pets", []):
            if pet not in ids:
                errors.append(f"union '{uid}' pet '{pet}' not in people")

    root = d.get("meta", {}).get("root")
    if root not in seen_uids:
        errors.append(f"meta.root '{root}' is not a known union id")

    # Everyone must be reachable from some household.
    placed = set()
    for u in unions:
        placed |= set(u.get("partners", [])) | set(u.get("children", [])) | set(u.get("pets", []))
    for pid in sorted(ids - placed):
        errors.append(f"'{pid}' ({people[pid].get('name')}) is defined but in no household")

    # A person may not be their own ancestor.
    parent_of: dict[str, list[str]] = {}
    for u in unions:
        for cid in u.get("children", []):
            parent_of.setdefault(cid, []).extend(u.get("partners", []))

    def loops(pid: str, seen: set[str]) -> bool:
        if pid in seen:
            return True
        seen = seen | {pid}
        return any(loops(par, seen) for par in parent_of.get(pid, []))

    for pid in ids:
        if loops(pid, set()):
            errors.append(f"'{pid}' is its own ancestor — circular link")
            break

    return errors


# ─────────────────────────── graph payload ───────────────────────────

def graph(d: dict) -> dict:
    """Everything the client needs to walk the tree, precomputed."""
    people = d["people"]
    unions = d["unions"]

    out_people = {}
    for pid, p in people.items():
        e = {"name": p["name"], "rel": p.get("rel", ""), "face": p.get("face", "👤")}
        if p.get("photo"):
            e["photo"] = p["photo"]
        if p.get("style"):
            e["style"] = p["style"]
        if p.get("badge"):
            e["badge"] = p["badge"]
        if p.get("note"):
            e["note"] = p["note"]
        if p.get("born") and p.get("died"):
            e["date"] = f"{pretty(p['born'])} – {pretty(p['died'])}"
        elif p.get("born"):
            e["date"] = f"Born {pretty(p['born'])}"
        elif p.get("due"):
            e["date"] = f"Due {pretty(p['due'])}"
        elif p.get("died"):
            e["date"] = f"Until {pretty(p['died'])}"
        out_people[pid] = e

    out_unions = {
        u["id"]: {
            "partners": u.get("partners", []),
            "children": u.get("children", []),
            "pets": u.get("pets", []),
            "label": u.get("label", ""),
        }
        for u in unions
    }

    # person -> unions they are a partner in / the union they were born into
    own, birth = {}, {}
    for u in unions:
        for pid in u.get("partners", []):
            own.setdefault(pid, []).append(u["id"])
        for cid in u.get("children", []):
            birth[cid] = u["id"]

    return {
        "people": out_people,
        "unions": out_unions,
        "own": own,
        "birth": birth,
        "root": d["meta"]["root"],
        "branches": d.get("branches", []),
        "questions": d.get("open_questions", []),
    }


# ─────────────────────────── CSS ───────────────────────────

CSS = r"""
    .tree-hero { background: linear-gradient(165deg, var(--sage-pale) 0%, var(--cream) 55%, var(--brown-pale) 100%); padding: 68px 24px 44px; text-align: center; }
    .tree-hero h1 { font-size: clamp(34px, 6.5vw, 62px); margin-bottom: 10px; }
    .tree-hero p { font-size: 17px; color: var(--text-secondary); max-width: 480px; margin: 0 auto; }

    /* ── Controls ─────────────────────────────────────── */
    .tree-controls { position: sticky; top: 0; z-index: 40; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: center;
      padding: 12px 16px; background: rgba(250,246,239,0.82); -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
      border-bottom: 1px solid rgba(122,158,126,0.18); }
    .tc-btn { font: inherit; font-size: 14px; font-weight: 600; color: var(--text-secondary); background: rgba(122,158,126,0.12); border: none;
      border-radius: var(--radius-full); padding: 9px 18px; cursor: pointer; display: inline-flex; align-items: center; gap: 7px;
      transition: background .2s ease, color .2s ease, transform .12s ease; }
    .tc-btn:hover { background: rgba(122,158,126,0.22); }
    .tc-btn:active { transform: scale(.96); }
    .tc-btn:focus-visible { outline: 3px solid var(--sage); outline-offset: 2px; }
    .tc-btn.primary { background: var(--forest); color: #fff; }
    .tc-btn.primary:hover { background: #2f5942; }
    .tc-search { position: relative; }
    .tc-search input { font: inherit; font-size: 14px; color: var(--text-primary); background: #fff; border: 1px solid rgba(122,158,126,0.28);
      border-radius: var(--radius-full); padding: 9px 16px 9px 36px; width: 190px; }
    .tc-search input:focus { outline: 3px solid var(--sage); outline-offset: 1px; border-color: var(--sage); }
    .tc-search::before { content: "🔍"; position: absolute; left: 13px; top: 50%; transform: translateY(-50%); font-size: 13px; pointer-events: none; opacity: .55; }
    .tc-results { position: absolute; top: calc(100% + 8px); left: 0; right: 0; background: #fff; border: 1px solid rgba(122,158,126,0.25);
      border-radius: var(--radius-md); box-shadow: 0 12px 36px rgba(60,40,20,0.16); overflow: hidden; max-height: 280px; overflow-y: auto; z-index: 50; }
    .tc-results:empty { display: none; }
    .tc-results button { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; font: inherit; font-size: 14px;
      background: none; border: none; padding: 11px 14px; cursor: pointer; color: var(--text-primary); }
    .tc-results button:hover, .tc-results button:focus { background: var(--sage-pale); outline: none; }
    .tc-results .r-rel { margin-left: auto; font-size: 11px; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: .05em; }

    /* ── Canvas ───────────────────────────────────────── */
    #tree-scroll { overflow-x: auto; overflow-y: hidden; padding: 40px 0 56px; -webkit-overflow-scrolling: touch; }
    #tree { display: flex; flex-direction: column; align-items: center; gap: 0; min-width: min-content; padding: 0 32px; }

    .level { display: flex; justify-content: center; align-items: flex-start; gap: 34px; }
    .level.ancestors { margin-bottom: 4px; }

    /* ── Household card ───────────────────────────────── */
    .house { display: flex; flex-direction: column; align-items: center; }
    .house-pair { position: relative; display: flex; gap: 20px; padding: 14px 16px 18px; background: rgba(255,255,255,0.62);
      border: 1px solid rgba(122,158,126,0.22); border-radius: var(--radius-lg); box-shadow: 0 2px 14px rgba(60,40,20,0.05); }
    .house-pair.is-root { background: linear-gradient(160deg, #fff, var(--sage-pale)); border-color: var(--sage); box-shadow: 0 8px 30px rgba(122,158,126,0.22); }
    .house-pair.two::before { content: ""; position: absolute; top: 52px; left: 50%; width: 20px; height: 2px; margin-left: -10px; background: var(--sage-light); border-radius: 2px; }
    .house-label { position: absolute; left: 50%; bottom: 5px; transform: translateX(-50%); font-size: 10.5px; font-weight: 600;
      letter-spacing: .06em; text-transform: uppercase; color: var(--text-tertiary); white-space: nowrap; }

    /* ── Person ───────────────────────────────────────── */
    .p { display: flex; flex-direction: column; align-items: center; width: 118px; background: none; border: none; padding: 0; cursor: pointer;
      font: inherit; color: inherit; border-radius: var(--radius-md); transition: transform .2s cubic-bezier(.22,.9,.3,1); }
    .p:hover { transform: translateY(-3px); }
    .p:active { transform: translateY(-1px) scale(.98); }
    .p:focus-visible { outline: 3px solid var(--sage); outline-offset: 4px; }
    .p-ring { position: relative; width: 66px; height: 66px; border-radius: var(--radius-full); background: var(--sage-pale); display: grid; place-items: center;
      font-size: 31px; overflow: hidden; border: 2.5px solid rgba(122,158,126,0.30); transition: border-color .2s ease, box-shadow .2s ease; }
    .p:hover .p-ring { border-color: var(--sage); box-shadow: 0 6px 18px rgba(122,158,126,0.28); }
    .p-ring img { width: 100%; height: 100%; object-fit: cover; }
    .p-name { margin-top: 9px; font-size: 13.5px; font-weight: 700; line-height: 1.22; letter-spacing: -0.015em; text-align: center; }
    .p-rel { margin-top: 3px; font-size: 10.5px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--sage); text-align: center; }

    .p.is-levi .p-ring { border-color: var(--terracotta); box-shadow: 0 0 0 4px rgba(196,113,74,0.14); }
    .p.is-levi .p-rel { color: var(--terracotta); }
    .p.is-baby .p-ring { border-style: dashed; border-color: var(--sage); }
    .p.is-pet .p-rel { color: var(--brown-light); }
    .p.is-memory .p-ring { filter: grayscale(1); opacity: .78; }
    .p.is-memory .p-rel { color: var(--mushroom); }
    .p.is-focus .p-ring { border-color: var(--forest); box-shadow: 0 0 0 4px rgba(61,107,82,0.16); }
    .p.dim { opacity: .34; }

    /* expandable affordance */
    .p-more { position: absolute; right: -3px; bottom: -3px; width: 23px; height: 23px; border-radius: var(--radius-full);
      background: var(--forest); color: #fff; font-size: 13px; font-weight: 700; display: grid; place-items: center;
      border: 2.5px solid var(--cream); transition: transform .25s cubic-bezier(.3,1.4,.5,1), background .2s ease; }
    .p.open .p-more { transform: rotate(45deg); background: var(--terracotta); }
    .p-badge { position: absolute; top: -4px; left: 50%; transform: translateX(-50%); background: var(--sage); color: #fff;
      font-size: 8.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; padding: 2px 7px; border-radius: var(--radius-full); white-space: nowrap; }

    /* ── Connectors ───────────────────────────────────── */
    .stem { width: 2px; height: 26px; background: var(--sage-light); }
    .stem.up { background: linear-gradient(180deg, rgba(178,205,181,0.25), var(--sage-light)); }
    .kids-wrap { display: flex; flex-direction: column; align-items: center; }
    .kids-bar { position: relative; height: 2px; background: var(--sage-light); border-radius: 2px; }
    .kids { display: flex; gap: 26px; align-items: flex-start; }
    .kid { display: flex; flex-direction: column; align-items: center; }
    .kid > .stem { height: 22px; }
    .pets { display: flex; gap: 20px; margin-top: 18px; padding-top: 16px; border-top: 1px dashed rgba(122,158,126,0.35); }

    /* ── Expansion animation ──────────────────────────── */
    .grow { animation: grow .42s cubic-bezier(.22,.9,.3,1); }
    @keyframes grow { from { opacity: 0; transform: translateY(-10px) scale(.96); } to { opacity: 1; transform: none; } }
    @media (prefers-reduced-motion: reduce) { .grow { animation: none; } .p, .p-more { transition: none; } }

    /* ── Detail sheet ─────────────────────────────────── */
    #sheet { position: fixed; inset: auto 0 0 0; z-index: 60; background: rgba(250,246,239,0.92);
      -webkit-backdrop-filter: saturate(180%) blur(28px); backdrop-filter: saturate(180%) blur(28px);
      border-top: 1px solid rgba(122,158,126,0.28); border-radius: var(--radius-xl) var(--radius-xl) 0 0;
      box-shadow: 0 -12px 48px rgba(60,40,20,0.18); padding: 26px 26px 32px; transform: translateY(102%);
      transition: transform .38s cubic-bezier(.22,.9,.3,1); max-height: 74vh; overflow-y: auto; }
    #sheet.on { transform: none; }
    @media (min-width: 760px) {
      #sheet { inset: auto auto 22px 22px; width: 348px; border-radius: var(--radius-xl); border: 1px solid rgba(122,158,126,0.28); transform: translateY(calc(100% + 32px)); }
    }
    .sheet-grip { width: 38px; height: 4px; background: rgba(122,158,126,0.4); border-radius: 2px; margin: -8px auto 18px; }
    .sheet-top { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
    .sheet-face { width: 58px; height: 58px; border-radius: var(--radius-full); background: var(--sage-pale); display: grid; place-items: center;
      font-size: 28px; overflow: hidden; border: 2px solid rgba(122,158,126,0.3); flex-shrink: 0; }
    .sheet-face img { width: 100%; height: 100%; object-fit: cover; }
    .sheet-top h2 { font-size: 21px; margin: 0; letter-spacing: -0.02em; }
    .sheet-top .s-rel { font-size: 11.5px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--sage); margin-top: 3px; }
    .sheet-note { font-size: 14.5px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 16px; }
    .sheet-rows { display: grid; gap: 9px; }
    .s-row { display: flex; gap: 10px; font-size: 13.5px; align-items: baseline; }
    .s-row dt { flex: 0 0 74px; color: var(--text-tertiary); font-weight: 600; }
    .s-row dd { margin: 0; color: var(--text-secondary); }
    .s-row dd button { font: inherit; font-size: 13.5px; color: var(--forest); background: none; border: none; padding: 0;
      cursor: pointer; text-decoration: underline; text-decoration-color: rgba(61,107,82,0.3); text-underline-offset: 2px; }
    .s-row dd button:hover { text-decoration-color: var(--forest); }
    .sheet-close { position: absolute; top: 18px; right: 20px; width: 30px; height: 30px; border-radius: var(--radius-full);
      background: rgba(122,158,126,0.14); border: none; cursor: pointer; font-size: 15px; color: var(--text-secondary); display: grid; place-items: center; }
    .sheet-close:hover { background: rgba(122,158,126,0.26); }
    .sheet-focus { margin-top: 18px; width: 100%; }

    /* ── More family drawer ───────────────────────────── */
    .more-wrap { max-width: 880px; margin: 0 auto; padding: 0 24px 72px; }
    .more-h { font-size: 13px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--text-tertiary);
      text-align: center; margin-bottom: 20px; }
    .more-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(255px, 1fr)); gap: 14px; }
    .more-b { background: rgba(255,255,255,0.68); border: 1px solid rgba(122,158,126,0.2); border-radius: var(--radius-lg); overflow: hidden; }
    .more-b summary { cursor: pointer; list-style: none; padding: 17px 20px; display: flex; align-items: center; gap: 11px;
      font-size: 16px; font-weight: 700; color: var(--forest); letter-spacing: -0.015em; }
    .more-b summary::-webkit-details-marker { display: none; }
    .more-b summary::after { content: "＋"; margin-left: auto; color: var(--text-tertiary); transition: transform .25s ease; }
    .more-b[open] summary::after { transform: rotate(45deg); }
    .more-b summary:focus-visible { outline: 3px solid var(--sage); outline-offset: -3px; }
    .more-b ul { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; padding: 0 20px 20px; }
    .more-b li { background: var(--sage-pale); color: var(--text-secondary); border-radius: var(--radius-full); padding: 5px 12px; font-size: 13px; }
    .qnote { max-width: 620px; margin: 30px auto 0; background: var(--brown-pale); border-left: 4px solid var(--terracotta);
      border-radius: var(--radius-md); padding: 18px 22px; font-size: 13.5px; color: var(--text-secondary); line-height: 1.65; }

    .hint { text-align: center; font-size: 13px; color: var(--text-tertiary); margin: 0 auto 6px; }
    @media (max-width: 640px) {
      .p { width: 96px; }
      .p-ring { width: 58px; height: 58px; font-size: 27px; }
      .level { gap: 22px; }
      .kids { gap: 16px; }
      #tree { padding: 0 18px; }
    }
"""


# ─────────────────────────── JS ───────────────────────────

JS = r"""
(function () {
  'use strict';
  var G = window.__FAMILY__;
  var P = G.people, U = G.unions, OWN = G.own, BIRTH = G.birth;

  var state = { root: G.root, open: {}, focus: null };

  var scroll = document.getElementById('tree-scroll');
  var tree   = document.getElementById('tree');
  var sheet  = document.getElementById('sheet');

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]; }); }

  /* Which households can this person open, other than the one shown? */
  function otherUnions(pid, shownUid) {
    return (OWN[pid] || []).filter(function (u) { return u !== shownUid; });
  }
  function canExpand(pid, shownUid) {
    if (otherUnions(pid, shownUid).length) return true;
    var b = BIRTH[pid];
    return !!(b && b !== shownUid);
  }

  /* ── build one person button ── */
  function personEl(pid, shownUid, opts) {
    opts = opts || {};
    var p = P[pid];
    var b = document.createElement('button');
    b.className = 'p' + (p.style ? ' ' + p.style.split(' ').map(function (s) { return 'is-' + s; }).join(' ') : '');
    if (state.focus === pid) b.className += ' is-focus';
    if (state.open[pid]) b.className += ' open';
    b.dataset.pid = pid;
    b.setAttribute('aria-label', p.name + (p.rel ? ', ' + p.rel : ''));

    var ring = '<div class="p-ring">' +
      (p.photo ? '<img src="' + esc(p.photo) + '" alt="" loading="lazy" decoding="async">' : esc(p.face)) +
      (p.badge ? '<span class="p-badge">' + esc(p.badge) + '</span>' : '') +
      (!opts.noExpand && canExpand(pid, shownUid) ? '<span class="p-more" aria-hidden="true">＋</span>' : '') +
      '</div>';

    b.innerHTML = ring +
      '<span class="p-name">' + esc(p.name) + '</span>' +
      '<span class="p-rel">' + esc(p.rel) + '</span>';

    b.addEventListener('click', function (e) {
      e.stopPropagation();
      openSheet(pid);
      if (canExpand(pid, shownUid)) toggle(pid, shownUid);
    });
    return b;
  }

  function toggle(pid, shownUid) {
    if (state.open[pid]) { delete state.open[pid]; }
    else {
      var others = otherUnions(pid, shownUid);
      state.open[pid] = others.length ? { kind: 'union', id: others[0] }
                                      : { kind: 'birth', id: BIRTH[pid] };
    }
    render();
  }

  /* ── household block ── */
  function houseEl(uid, opts) {
    opts = opts || {};
    var u = U[uid];
    var wrap = document.createElement('div');
    wrap.className = 'house';

    var pair = document.createElement('div');
    pair.className = 'house-pair' + (u.partners.length === 2 ? ' two' : '') + (opts.isRoot ? ' is-root' : '');
    u.partners.forEach(function (pid) { pair.appendChild(personEl(pid, uid)); });
    if (u.label) {
      var l = document.createElement('span');
      l.className = 'house-label';
      l.textContent = u.label;
      pair.appendChild(l);
    }
    wrap.appendChild(pair);

    var kids = (u.children || []).slice();
    var pets = (u.pets || []).slice();

    if (kids.length) {
      wrap.appendChild(stem());
      var kw = document.createElement('div');
      kw.className = 'kids-wrap';
      var bar = document.createElement('div');
      bar.className = 'kids-bar';
      var row = document.createElement('div');
      row.className = 'kids';
      kids.forEach(function (cid) {
        var k = document.createElement('div');
        k.className = 'kid';
        k.appendChild(stem());
        k.appendChild(personEl(cid, uid));
        var st = state.open[cid];
        if (st) {
          var sub = document.createElement('div');
          sub.className = 'grow';
          sub.style.marginTop = '4px';
          sub.appendChild(stem());
          sub.appendChild(houseEl(st.id));
          k.appendChild(sub);
        }
        row.appendChild(k);
      });
      kw.appendChild(bar);
      kw.appendChild(row);
      wrap.appendChild(kw);
      requestAnimationFrame(function () {
        if (row.children.length > 1) {
          var f = row.children[0].getBoundingClientRect();
          var l = row.children[row.children.length - 1].getBoundingClientRect();
          bar.style.width = Math.max(2, (l.left + l.width / 2) - (f.left + f.width / 2)) + 'px';
        } else { bar.style.width = '2px'; }
      });
    }

    if (pets.length) {
      var pd = document.createElement('div');
      pd.className = 'pets';
      pets.forEach(function (x) { pd.appendChild(personEl(x, uid, { noExpand: true })); });
      wrap.appendChild(pd);
    }
    return wrap;
  }

  function stem(up) {
    var s = document.createElement('div');
    s.className = 'stem' + (up ? ' up' : '');
    return s;
  }

  /* ── ancestors above the root ── */
  function ancestorsEl(uid) {
    var u = U[uid], boxes = [];
    u.partners.forEach(function (pid) {
      var b = BIRTH[pid];
      if (!b) return;
      var col = document.createElement('div');
      col.style.display = 'flex';
      col.style.flexDirection = 'column';
      col.style.alignItems = 'center';
      var pu = U[b], pair = document.createElement('div');
      pair.className = 'house-pair' + (pu.partners.length === 2 ? ' two' : '');
      pu.partners.forEach(function (x) { pair.appendChild(personEl(x, b)); });
      if (pu.label) {
        var l = document.createElement('span');
        l.className = 'house-label';
        l.textContent = pu.label;
        pair.appendChild(l);
      }
      col.appendChild(pair);
      col.appendChild(stem(true));
      boxes.push(col);
    });
    if (!boxes.length) return null;
    var lvl = document.createElement('div');
    lvl.className = 'level ancestors';
    boxes.forEach(function (b) { lvl.appendChild(b); });
    return lvl;
  }

  /* ── render ── */
  function render() {
    var x = scroll.scrollLeft, y = window.scrollY;
    tree.textContent = '';
    var anc = ancestorsEl(state.root);
    if (anc) tree.appendChild(anc);
    tree.appendChild(houseEl(state.root, { isRoot: true }));
    scroll.scrollLeft = x;
    window.scrollTo(0, y);
    document.getElementById('btn-reset').hidden =
      (state.root === G.root && !Object.keys(state.open).length);
  }

  /* ── detail sheet ── */
  function relatives(pid) {
    var out = [];
    (OWN[pid] || []).forEach(function (uid) {
      var u = U[uid];
      u.partners.forEach(function (x) { if (x !== pid) out.push(['Partner', x]); });
      (u.children || []).forEach(function (c) { out.push(['Child', c]); });
    });
    var b = BIRTH[pid];
    if (b) {
      U[b].partners.forEach(function (x) { out.push(['Parent', x]); });
      (U[b].children || []).forEach(function (c) { if (c !== pid) out.push(['Sibling', c]); });
    }
    return out;
  }

  function openSheet(pid) {
    var p = P[pid];
    state.focus = pid;
    var groups = {};
    relatives(pid).forEach(function (r) {
      (groups[r[0]] = groups[r[0]] || []).push(r[1]);
    });

    var rows = '';
    if (p.date) rows += '<div class="s-row"><dt>' + (p.style && p.style.indexOf('memory') > -1 ? 'Years' : 'Born') + '</dt><dd>' + esc(p.date) + '</dd></div>';
    ['Parent', 'Partner', 'Sibling', 'Child'].forEach(function (k) {
      if (!groups[k]) return;
      var label = { Parent: 'Parents', Partner: 'Partner', Sibling: 'Brothers &amp; sisters', Child: 'Children' }[k];
      var links = groups[k].map(function (id) {
        return '<button data-goto="' + id + '">' + esc(P[id].name) + '</button>';
      }).join(', ');
      rows += '<div class="s-row"><dt>' + label + '</dt><dd>' + links + '</dd></div>';
    });

    sheet.innerHTML =
      '<div class="sheet-grip" aria-hidden="true"></div>' +
      '<button class="sheet-close" aria-label="Close">✕</button>' +
      '<div class="sheet-top">' +
        '<div class="sheet-face">' + (p.photo ? '<img src="' + esc(p.photo) + '" alt="">' : esc(p.face)) + '</div>' +
        '<div><h2>' + esc(p.name) + '</h2><div class="s-rel">' + esc(p.rel) + '</div></div>' +
      '</div>' +
      (p.note ? '<p class="sheet-note">' + esc(p.note) + '</p>' : '') +
      '<dl class="sheet-rows">' + rows + '</dl>' +
      ((OWN[pid] || []).length ? '<button class="tc-btn primary sheet-focus" data-root="' + esc((OWN[pid] || [])[0]) + '">Start the tree here</button>' : '');

    sheet.classList.add('on');
    render();
  }

  function closeSheet() {
    sheet.classList.remove('on');
    state.focus = null;
    render();
  }

  sheet.addEventListener('click', function (e) {
    var c = e.target.closest('.sheet-close');
    if (c) return closeSheet();
    var g = e.target.closest('[data-goto]');
    if (g) return openSheet(g.dataset.goto);
    var r = e.target.closest('[data-root]');
    if (r) {
      state.root = r.dataset.root;
      state.open = {};
      closeSheet();
      scroll.scrollTo({ left: 0, behavior: 'smooth' });
      window.scrollTo({ top: scroll.offsetTop - 70, behavior: 'smooth' });
    }
  });

  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSheet(); });

  /* ── controls ── */
  document.getElementById('btn-reset').addEventListener('click', function () {
    state.root = G.root; state.open = {}; closeSheet();
    scroll.scrollTo({ left: 0, behavior: 'smooth' });
  });

  document.getElementById('btn-all').addEventListener('click', function () {
    var expanded = Object.keys(state.open).length > 0;
    state.open = {};
    if (!expanded) {
      Object.keys(U).forEach(function (uid) {
        (U[uid].children || []).forEach(function (cid) {
          var o = otherUnions(cid, uid);
          if (o.length) state.open[cid] = { kind: 'union', id: o[0] };
        });
      });
    }
    this.textContent = expanded ? 'Expand all' : 'Collapse all';
    render();
  });

  /* ── search ── */
  var input = document.getElementById('q'), results = document.getElementById('results');
  input.addEventListener('input', function () {
    var v = input.value.trim().toLowerCase();
    results.textContent = '';
    if (v.length < 2) return;
    Object.keys(P).filter(function (id) {
      return P[id].name.toLowerCase().indexOf(v) > -1;
    }).slice(0, 8).forEach(function (id) {
      var b = document.createElement('button');
      b.innerHTML = '<span>' + esc(P[id].face) + '</span><span>' + esc(P[id].name) +
        '</span><span class="r-rel">' + esc(P[id].rel) + '</span>';
      b.addEventListener('click', function () {
        input.value = ''; results.textContent = '';
        var u = (OWN[id] || [])[0] || BIRTH[id];
        if (u) { state.root = u; state.open = {}; }
        openSheet(id);
      });
      results.appendChild(b);
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.tc-search')) results.textContent = '';
  });

  render();
})();
"""


# ─────────────────────────── page ───────────────────────────

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
          <li><a href="levi-family-tree.html" role="menuitem">Family Tree</a></li>
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


def render_more(d: dict) -> str:
    if not d.get("branches"):
        return ""
    cards = ""
    for b in d["branches"]:
        items = "".join(f"<li>{escape(m)}</li>" for m in b["members"])
        cards += (
            '        <details class="more-b">\n'
            f'          <summary><span>{b["emoji"]}</span> {escape(b["title"])}</summary>\n'
            f"          <ul>{items}</ul>\n"
            "        </details>\n"
        )
    q = d.get("open_questions", [])
    qs = ""
    if q:
        qs = ('      <div class="qnote"><b>Still to confirm:</b> '
              + " ".join(escape(x) for x in q) + "</div>\n")
    return (
        '  <section class="more-wrap">\n'
        '    <p class="more-h">More Family</p>\n'
        '    <div class="more-grid">\n'
        f"{cards}"
        "    </div>\n"
        f"{qs}"
        "  </section>\n"
    )


def build(d: dict) -> str:
    m = d["meta"]
    payload = json.dumps(graph(d), ensure_ascii=False, separators=(",", ":"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="robots" content="noindex, nofollow"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>
  <meta name="description" content="The McGee family tree — tap anyone to meet their family."/>
  <title>{escape(m['title'])} · McGee Family</title>
  <!-- ══════════════════════════════════════════════════════════
       GENERATED FILE — DO NOT EDIT BY HAND
       Source:  data/family.json
       Rebuild: double-click "Update Family Tree.command"
       Built:   {date.today().isoformat()}
       ══════════════════════════════════════════════════════════ -->
  <meta property="og:type"        content="website"/>
  <meta property="og:site_name"   content="The McGee Family"/>
  <meta property="og:url"         content="https://mcgeefamily2025.com/levi-family-tree.html"/>
  <meta property="og:title"       content="{escape(m['title'])} · McGee Family"/>
  <meta property="og:description" content="Tap anyone to meet their family."/>
  <meta name="theme-color"        content="#7A9E7E"/>
  <link rel="manifest" href="manifest.json"/>
  <meta name="mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-title" content="McGee Family"/>
  <link rel="icon" type="image/svg+xml" href="favicon.svg"/>
  <link rel="canonical" href="https://mcgeefamily2025.com/levi-family-tree.html"/>
  <link rel="stylesheet" href="css/style.css"/>
  <style>{CSS}  </style>
</head>
<body>

{NAV}

  <header class="tree-hero">
    <h1>{escape(m['title'])}</h1>
    <p>{escape(m['intro'])}</p>
  </header>

  <div class="tree-controls">
    <div class="tc-search">
      <input type="search" id="q" placeholder="Find someone" aria-label="Find a family member" autocomplete="off"/>
      <div id="results" class="tc-results" role="listbox"></div>
    </div>
    <button class="tc-btn" id="btn-all">Expand all</button>
    <button class="tc-btn primary" id="btn-reset" hidden>Back to Mom &amp; Dad</button>
  </div>

  <p class="hint">Tap a circle with a <b>＋</b> to open that person's family.</p>

  <div id="tree-scroll">
    <div id="tree"></div>
  </div>

  <div id="sheet" role="dialog" aria-modal="false" aria-label="Person details"></div>

{render_more(d)}
  <footer class="footer">
    <div class="container">
      <p class="footer-tagline">Faith. Family. Forever.</p>
      <p class="footer-note">The McGee Family · Queen Creek, Arizona</p>
    </div>
  </footer>

  <script src="js/main.js"></script>
  <script>window.__FAMILY__ = {payload};</script>
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

    print(f"\033[1;32m✓ Data valid\033[0m — {len(d['people'])} people, "
          f"{len(d['unions'])} households, root = '{d['meta']['root']}'")
    if q := d.get("open_questions"):
        print(f"\033[1;33m⚠ {len(q)} open question(s)\033[0m — note renders on the page")

    if check:
        print("  (--check: nothing written)")
        return

    OUT.write_text(build(d), encoding="utf-8")
    print(f"\033[1;32m✓ Wrote\033[0m {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
