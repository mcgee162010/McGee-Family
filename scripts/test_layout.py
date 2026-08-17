#!/usr/bin/env python3
"""
Stress-test the family tree layout engine at multiple scales.

Generates synthetic families (10 / 50 / 120 / 520 people), runs the SAME
layout algorithm the browser uses (ported 1:1 from the JS), and asserts:

  * no two person cards overlap
  * children are always on a lower generation than their parents
  * every person is placed exactly once
  * aspect ratio stays sane (tree doesn't degenerate into a 1-px-tall ribbon)
  * layout completes in reasonable time

Usage:  python3 scripts/test_layout.py
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NW, NH, GAPX, GAPY, PODGAP = 140, 62, 26, 118, 16


# ── the layout engine, ported from the JS in build_family_tree.py ──────────

def compute_gen(people, unions, birth):
    gen = {p: 0 for p in people if p not in birth}
    for _ in range(60):
        moved = False
        for u in unions.values():
            g = max([gen.get(p, 0) for p in u["partners"]] or [0])
            for p in u["partners"]:
                if gen.get(p, 0) != g:
                    gen[p] = g
                    moved = True
            for c in u.get("children", []):
                if gen.get(c, 0) < g + 1:
                    gen[c] = g + 1
                    moved = True
        if not moved:
            break
    for p in people:
        gen.setdefault(p, 0)
    return gen


def layout(people, unions, own, birth, big=140):
    gen = compute_gen(people, unions, birth)
    pos, done, order = {}, set(), []
    cursor = [0.0]
    collapsed, hidden = {}, set()

    def kids_of(pid):
        out = []
        for uid in own.get(pid, []):
            for c in unions[uid].get("children", []):
                if c not in out:
                    out.append(c)
        return out

    def descendants_of(pid):
        out, q = set(), list(kids_of(pid))
        while q:
            x = q.pop()
            if x in out:
                continue
            out.add(x)
            q.extend(kids_of(x))
        return out

    # Level-of-detail: mirror the browser's auto-collapse on very large trees.
    if len(people) > big:
        anchor = next(iter(people))
        near = {anchor} | descendants_of(anchor)
        for p in people:
            if p not in near and len(kids_of(p)) > 2:
                collapsed[p] = True
        for p, on in collapsed.items():
            if on:
                hidden |= descendants_of(p)

    def spouses_of(pid):
        out = []
        for uid in own.get(pid, []):
            for x in unions[uid]["partners"]:
                if x != pid and x not in out:
                    out.append(x)
        return out

    def seeds_own_pod(pid):
        if pid in birth:
            return True
        if kids_of(pid):
            return True
        return not spouses_of(pid)

    def pod_members(pid):
        m = [pid]
        for uid in own.get(pid, []):
            for x in unions[uid]["partners"]:
                if x == pid or x in done or x in hidden or x in m:
                    continue
                if not seeds_own_pod(x):
                    m.append(x)
        return m

    def place(pid):
        if pid in done or pid in hidden:
            return None
        mem = pod_members(pid)
        done.update(mem)
        w = len(mem) * NW + (len(mem) - 1) * PODGAP

        ch = []
        if not collapsed.get(pid):
            for uid in own.get(pid, []):
                for c in unions[uid].get("children", []) + unions[uid].get("pets", []):
                    if c not in done and c not in hidden:
                        ch.append(c)

        if not ch:
            left = cursor[0]
        else:
            spans = [s for s in (place(c) for c in ch) if s]
            if not spans:
                left = cursor[0]
            else:
                mid = (spans[0][0] + spans[-1][1]) / 2
                left = max(cursor[0], mid - w / 2)
        cursor[0] = max(cursor[0], left + w + GAPX)
        for i, m in enumerate(mem):
            pos[m] = (left + i * (NW + PODGAP), gen[m] * (NH + GAPY))
            order.append(m)
        return (left, left + w)

    roots = sorted([p for p in people
                    if p not in birth and p not in hidden and kids_of(p)],
                   key=lambda p: gen[p])
    for r in roots:
        place(r)
    for p in people:
        place(p)
    return pos, gen, order, hidden


# ── synthetic family generator ────────────────────────────────────────────

def make_family(target, seed=7):
    rnd = random.Random(seed)
    people, unions, own, birth = {}, {}, {}, {}
    n = [0]

    def person():
        n[0] += 1
        pid = f"p{n[0]}"
        people[pid] = {"name": f"Person {n[0]}"}
        return pid

    def marry(a, b, kids):
        uid = f"u{len(unions)}"
        unions[uid] = {"id": uid, "partners": [a, b], "children": kids, "pets": []}
        own.setdefault(a, []).append(uid)
        own.setdefault(b, []).append(uid)
        for k in kids:
            birth[k] = uid
        return uid

    def grow(depth):
        a, b = person(), person()
        kids = []
        if depth > 0:
            for _ in range(rnd.randint(1, 4)):
                if len(people) >= target:
                    break
                kids.append(grow(depth - 1))
        marry(a, b, kids)
        return a

    while len(people) < target:
        grow(rnd.randint(2, 4))
    return people, unions, own, birth


# ── assertions ────────────────────────────────────────────────────────────

def check(label, people, unions, own, birth, root_uid=None):
    t0 = time.perf_counter()
    pos, gen, order, hidden = layout(people, unions, own, birth)
    ms = (time.perf_counter() - t0) * 1000
    fails = []

    # every visible person placed exactly once
    visible = len(people) - len(hidden)
    if len(pos) != visible:
        fails.append(f"placed {len(pos)} of {visible} visible people")
    if len(order) != len(set(order)):
        fails.append("a person was placed more than once")

    # no overlapping cards
    rows = {}
    for pid, (x, y) in pos.items():
        rows.setdefault(y, []).append((x, pid))
    overlaps = 0
    for y, items in rows.items():
        items.sort()
        for i in range(len(items) - 1):
            if items[i][0] + NW > items[i + 1][0] + 0.01:
                overlaps += 1
    if overlaps:
        fails.append(f"{overlaps} overlapping card pair(s)")

    # children strictly below parents
    bad = 0
    for u in unions.values():
        pg = [gen[p] for p in u["partners"] if p in gen]
        for c in u.get("children", []):
            if c in gen and pg and gen[c] <= min(pg):
                bad += 1
    if bad:
        fails.append(f"{bad} child/parent generation inversion(s)")

    # sane aspect
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    w = max(xs) - min(xs) + NW
    h = max(ys) - min(ys) + NH
    ratio = w / max(h, 1)
    if ratio > 80:
        fails.append(f"degenerate aspect ratio {ratio:.0f}:1")

    # LEGIBILITY of the DEFAULT view. fit-all is an explicit "show me
    # everything" gesture where small is acceptable — but the view the user
    # LANDS on must be readable. homeView() shows the root household plus one
    # generation each way, so measure that subset.
    def home_set():
        u = unions.get(root_uid)
        if not u:
            return list(pos)[:8]
        s = list(u["partners"])
        for p in u["partners"]:
            b = birth.get(p)
            if b:
                s += unions[b]["partners"]
            s += spouses_of_g(p)
        s += u.get("children", []) + u.get("pets", [])
        return [x for x in s if x in pos] or list(pos)[:8]

    def spouses_of_g(pid):
        out = []
        for uid in own.get(pid, []):
            for x in unions[uid]["partners"]:
                if x != pid and x not in out:
                    out.append(x)
        return out

    hs = home_set()
    hx = [pos[p][0] for p in hs]
    hy = [pos[p][1] for p in hs]
    hw = max(hx) - min(hx) + NW
    hh = max(hy) - min(hy) + NH
    hk = min(1440 / hw, 740 / hh) * 0.82
    hk = max(0.75, min(hk, 1.55))          # the scale floor in the shipped code
    home_px = 12.5 * hk
    if home_px < 9:
        fails.append(f"default view renders names at {home_px:.1f}px — unreadable")

    if ms > 2500:
        fails.append(f"layout took {ms:.0f} ms")

    status = "\033[1;32mPASS\033[0m" if not fails else "\033[1;31mFAIL\033[0m"
    col = f"{len(pos)}/{len(people)}" if hidden else str(len(people))
    print(f"  {status}  {label:<26} {col:>9} shown · "
          f"{len(unions):>3} unions · {max(gen.values())+1} gens · "
          f"{w:>6.0f}×{h:<5.0f} · {ms:>6.1f} ms")
    for f in fails:
        print(f"          \033[1;31m→ {f}\033[0m")
    return not fails


def main():
    print("\n\033[1mLayout engine stress test\033[0m\n")
    ok = True

    # the real family
    d = json.loads((ROOT / "data" / "family.json").read_text(encoding="utf-8"))
    people = d["people"]
    unions, own, birth = {}, {}, {}
    for u in d["unions"]:
        unions[u["id"]] = u
        for p in u.get("partners", []):
            own.setdefault(p, []).append(u["id"])
        for c in u.get("children", []):
            birth[c] = u["id"]
    ok &= check("real McGee family", people, unions, own, birth, d["meta"]["root"])

    for size in (10, 50, 120, 520):
        p, u, o, b = make_family(size)
        ok &= check(f"synthetic ~{size}", p, u, o, b, next(iter(u)))

    print()
    if ok:
        print("\033[1;32m✓ All layout tests passed\033[0m\n")
    else:
        print("\033[1;31m✗ Layout tests failed\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
