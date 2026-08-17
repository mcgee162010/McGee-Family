#!/usr/bin/env python3
"""
Generate small, square, web-optimized thumbnails for the family tree circles.

Reads the 'photo' path of every person in data/family.json, and writes a
256x256 center-cropped JPEG into photos/tree/ named <id>.jpg.
The JSON is then updated to point at the thumbnail.

Originals are never modified. Never uses `sips` (it corrupts files to black).

Usage:
    /usr/bin/python3 scripts/make_thumbs.py            # generate + rewrite JSON
    /usr/bin/python3 scripts/make_thumbs.py --dry-run  # report only
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit(
        "Pillow not available for this interpreter.\n"
        "Run with the system Python that has it:\n"
        "  /usr/bin/python3 scripts/make_thumbs.py"
    )

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "family.json"
DEST = ROOT / "photos" / "tree"

SIZE = 256          # rendered at 66px, so 256 covers 3x retina
QUALITY = 82


def parse_crop(crop: str | None) -> tuple[float, float]:
    """'26% 40%' -> (0.26, 0.40). Defaults to dead center."""
    if not crop:
        return (0.5, 0.5)
    nums = re.findall(r"([\d.]+)\s*%", crop)
    if len(nums) != 2:
        return (0.5, 0.5)
    return (float(nums[0]) / 100, float(nums[1]) / 100)


def square_crop(im: Image.Image, fx: float, fy: float, zoom: float) -> Image.Image:
    """
    Take a square window centred on the focal point.

    fx/fy are the focal point as a fraction of the full image (0-1).
    zoom > 1 tightens in: zoom=2 uses a window half the size of the short edge,
    which is what makes a single face usable inside a 66px circle.
    """
    w, h = im.size
    side = max(32, int(min(w, h) / max(zoom, 0.01)))
    cx, cy = fx * w, fy * h
    left = round(cx - side / 2)
    top = round(cy - side / 2)
    left = max(0, min(left, w - side))
    top = max(0, min(top, h - side))
    return im.crop((left, top, left + side, top + side))


def main() -> None:
    dry = "--dry-run" in sys.argv
    raw = DATA.read_text(encoding="utf-8")
    data = json.loads(raw)
    DEST.mkdir(parents=True, exist_ok=True)

    saved_before = saved_after = 0
    rewrites: list[tuple[str, str]] = []

    for pid, person in data["people"].items():
        src_rel = person.get("src") or person.get("photo")
        if not src_rel:
            continue
        src = ROOT / src_rel
        if not src.is_file():
            print(f"  ⚠ {pid}: missing {src_rel}")
            continue

        out_rel = f"photos/tree/{pid}.jpg"
        out = ROOT / out_rel

        before = src.stat().st_size
        saved_before += before

        if not dry:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)          # honor iPhone rotation
                im = im.convert("RGB")
                fx, fy = parse_crop(person.get("crop"))
                zoom = float(person.get("zoom", 1))
                im = square_crop(im, fx, fy, zoom)
                im = im.resize((SIZE, SIZE), Image.LANCZOS)
                im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            after = out.stat().st_size
        else:
            after = 0

        saved_after += after
        pct = (1 - after / before) * 100 if before and after else 0
        print(f"  {pid:<9} {before/1024:>8.0f} KB → {after/1024:>6.0f} KB  ({pct:.0f}% smaller)")

        if src_rel != out_rel:
            rewrites.append((pid, src_rel, out_rel))

    if dry:
        print("\n  (--dry-run: nothing written)")
        return

    # Rewrite JSON: preserve 'src' + 'crop' + 'zoom' so thumbs can be re-cut later.
    text = raw
    for pid, src_rel, out_rel in rewrites:
        if src_rel == out_rel:
            continue
        # Point 'photo' at the thumbnail, and remember the original as 'src'.
        text = text.replace(
            f'"photo": "{src_rel}"',
            f'"photo": "{out_rel}", "src": "{src_rel}"',
        )
    DATA.write_text(text, encoding="utf-8")

    print(f"\n  Total: {saved_before/1024:.0f} KB → {saved_after/1024:.0f} KB "
          f"({(1 - saved_after/saved_before)*100:.0f}% smaller)")
    print(f"  Updated {DATA.relative_to(ROOT)}")
    print("\n  Next: python3 scripts/build_family_tree.py")


if __name__ == "__main__":
    main()
