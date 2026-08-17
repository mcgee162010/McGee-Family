#!/usr/bin/env python3
"""
Shrink the site's tracked photos so GitHub Pages can deploy.

Two passes:
  1. DEDUPE  — find byte-identical files and keep one canonical copy.
  2. RESIZE  — cap every photo at MAX_EDGE px, re-encode as progressive JPEG.

Originals live in iCloud; the repo only ever held copies, so this is safe.
Never uses `sips` (it corrupts files to black). Pillow + shutil only.

Usage:
    /usr/bin/python3 scripts/shrink_photos.py --dry-run    # report only
    /usr/bin/python3 scripts/shrink_photos.py              # do it
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow missing for this interpreter. Use: /usr/bin/python3 "
             "scripts/shrink_photos.py")

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "photos"

MAX_EDGE = 2000        # plenty for full-screen retina viewing
QUALITY = 82
SKIP_DIRS = {"tree"}   # already-optimized 256px thumbnails

# When the same image exists in several folders, prefer these (in order).
PREFER = ["family-photoshoot", "wedding", "levi", "brittney", "bentley",
          "phoenix", "honeymoon", "engagement", "baby-mcgee", "family",
          "levi-birthday", "vows", "misc"]


def mb(n: int) -> float:
    return n / 1_048_576


def tracked_photos() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z", "photos"],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    files = []
    for rel in out.stdout.split("\0"):
        if not rel:
            continue
        p = ROOT / rel
        if not p.is_file():
            continue
        if p.parent.name in SKIP_DIRS:
            continue
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic", ".webp"}:
            continue
        files.append(p)
    return files


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rank(p: Path) -> tuple[int, int, str]:
    folder = p.parent.name
    pref = PREFER.index(folder) if folder in PREFER else len(PREFER)
    # prefer lowercase names (GitHub Pages is case-sensitive)
    return (pref, 0 if p.name == p.name.lower() else 1, str(p))


def which_reference(path_rel: str) -> bool:
    """Is this path referenced anywhere in the site's HTML/JSON/JS?"""
    r = subprocess.run(["git", "grep", "-l", "--", path_rel],
                       cwd=ROOT, capture_output=True, text=True)
    return bool(r.stdout.strip())


def main() -> None:
    dry = "--dry-run" in sys.argv
    files = tracked_photos()
    total_before = sum(f.stat().st_size for f in files)

    print(f"\n\033[1mPhoto shrink\033[0m — {len(files)} tracked photos, "
          f"{mb(total_before):,.0f} MB\n")

    # ── pass 1: dedupe ────────────────────────────────────────────────
    print("\033[1m1. Finding exact duplicates…\033[0m")
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        by_hash[digest(f)].append(f)

    to_delete: list[Path] = []
    for h, group in by_hash.items():
        if len(group) < 2:
            continue
        group.sort(key=rank)
        keeper = group[0]
        for dup in group[1:]:
            rel = str(dup.relative_to(ROOT))
            # never delete something the site actually links to
            if which_reference(rel):
                continue
            to_delete.append(dup)

    freed = sum(f.stat().st_size for f in to_delete)
    print(f"   {len(to_delete)} duplicate files → frees {mb(freed):,.0f} MB")

    if not dry and to_delete:
        rels = [str(f.relative_to(ROOT)) for f in to_delete]
        for i in range(0, len(rels), 200):
            subprocess.run(["git", "rm", "-q", "--"] + rels[i:i + 200],
                           cwd=ROOT, check=True)
        print(f"   \033[1;32m✓ removed\033[0m")

    remaining = [f for f in files if f not in set(to_delete)]

    # ── pass 2: resize ────────────────────────────────────────────────
    print(f"\n\033[1m2. Resizing {len(remaining)} photos to ≤{MAX_EDGE}px…\033[0m")
    before = after = 0
    changed = skipped = 0
    for f in remaining:
        if not f.is_file():
            continue
        b = f.stat().st_size
        before += b
        try:
            with Image.open(f) as im:
                w, h = im.size
                need = max(w, h) > MAX_EDGE or b > 500_000
                if not need:
                    after += b
                    skipped += 1
                    continue
                if dry:
                    after += int(b * 0.12)   # rough estimate for the report
                    changed += 1
                    continue
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
                tmp = f.with_suffix(f.suffix + ".tmp")
                im.save(tmp, "JPEG", quality=QUALITY, optimize=True,
                        progressive=True)
            if tmp.stat().st_size < b:
                shutil.move(str(tmp), str(f))
            else:
                tmp.unlink(missing_ok=True)
            after += f.stat().st_size
            changed += 1
        except Exception as e:                      # noqa: BLE001
            print(f"   ⚠ {f.name}: {e}")
            after += b

    print(f"   resized {changed}, left alone {skipped}")
    print(f"   {mb(before):,.0f} MB → {mb(after):,.0f} MB")

    total_after = after
    print(f"\n\033[1mResult\033[0m  {mb(total_before):,.0f} MB → "
          f"{mb(total_after):,.0f} MB  "
          f"(\033[1;32m{(1 - total_after / total_before) * 100:.0f}% smaller\033[0m)")
    limit = 1024
    print(f"        GitHub Pages limit {limit} MB — "
          + ("\033[1;32mwell under\033[0m" if mb(total_after) < 500
             else "\033[1;33mstill large\033[0m"))

    if dry:
        print("\n  (--dry-run: nothing changed)\n")
    else:
        print("\n  Next: git add -A photos && git commit && git push\n")


if __name__ == "__main__":
    main()
