#!/usr/bin/python3
"""
McGee Family Website — Annual Photo Book Export Script
=======================================================
Packages all photos from a given year into a single organized folder,
ready for upload to Artifact Uprising, Printful, or any print service.

Usage:
  python3 scripts/export_photobook.py          # exports current year
  python3 scripts/export_photobook.py 2025     # exports a specific year
  python3 scripts/export_photobook.py all      # exports all years

Output:
  ~/Desktop/McGee-Photobook-{YEAR}/
    01_Family/
    02_Wedding/
    03_Honeymoon/
    04_Engagement/
    05_Levi/
    06_LeviBirthday/
    07_Phoenix/
    08_Bentley/
    09_BabyMcGee/
    COVER.jpg        (first family photo — used as cover)
    INDEX.txt        (manifest of all included photos + captions)

Notes:
  - Copies only — never modifies originals
  - Uses shutil.copy2 (no sips, no compression)
  - Skips videos (.mov, .mp4)
  - Lowercase .jpg / .jpeg enforced for cross-platform compatibility
  - Run this every December to build that year's physical book
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────

SITE_ROOT  = Path("/Users/benjamin_mcgee/Documents/Enchanté/Conversations/4A2C3E4D-5130-4C0E-ACB6-B12ED50E5737/mcgee-family")
PHOTOS_DIR = SITE_ROOT / "photos"
EXPORT_BASE = Path.home() / "Desktop"

PHOTO_EXTS = {".jpg", ".jpeg", ".png"}

# Map folder → display name → recommended print order
FOLDER_ORDER = [
    ("family",        "01_Family",        "Family Photos"),
    ("wedding",       "02_Wedding",       "Wedding · November 1, 2025 · Greer, Arizona"),
    ("honeymoon",     "03_Honeymoon",     "Honeymoon · Thailand · November 2025"),
    ("engagement",    "04_Engagement",    "Engagement · October 30, 2024 · Riverview Park"),
    ("levi",          "05_Levi",          "Levi · Growing Up"),
    ("levi-birthday", "06_LeviBirthday",  "Levi's 7th Golden Birthday · April 7, 2026"),
    ("phoenix",       "07_Phoenix",       "Phoenix · Our German Shorthair Pointer"),
    ("bentley",       "08_Bentley",       "Bentley · In Loving Memory · 2015 – April 9, 2026"),
    ("baby-mcgee",    "09_BabyMcGee",     "Baby McGee · Coming September 4, 2026"),
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def is_photo(p: Path) -> bool:
    return p.suffix.lower() in PHOTO_EXTS and not p.name.startswith(".")

# ── EXPORT ────────────────────────────────────────────────────────────────────

def export_year(year: str) -> Path:
    export_dir = EXPORT_BASE / f"McGee-Photobook-{year}"

    if export_dir.exists():
        log(f"⚠️  Export folder already exists: {export_dir}")
        response = input("   Overwrite? (yes/no): ").strip().lower()
        if response != "yes":
            log("Cancelled.")
            sys.exit(0)
        shutil.rmtree(export_dir)

    export_dir.mkdir(parents=True)
    log(f"📁 Created export folder: {export_dir}")

    manifest_lines = [
        f"McGee Family Photo Book — {year}",
        f"Exported: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        f"Site: https://mcgeefamily2025.com",
        "=" * 60,
        "",
    ]

    total = 0
    cover_set = False

    for src_folder, dest_folder, label in FOLDER_ORDER:
        src_dir  = PHOTOS_DIR / src_folder
        dest_dir = export_dir / dest_folder

        if not src_dir.exists():
            log(f"   ⏭  Skipping {src_folder} (not found)")
            continue

        photos = sorted([f for f in src_dir.iterdir() if is_photo(f)])
        if not photos:
            log(f"   ⏭  Skipping {src_folder} (empty)")
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        manifest_lines.append(f"\n── {label} ({len(photos)} photos) ──")

        for photo in photos:
            dest_name = photo.stem + photo.suffix.lower()
            dest_path = dest_dir / dest_name
            shutil.copy2(photo, dest_path)
            manifest_lines.append(f"  {dest_folder}/{dest_name}")
            total += 1

            # Set the cover image (first family photo)
            if not cover_set and src_folder == "family":
                cover_dest = export_dir / "COVER.jpg"
                shutil.copy2(photo, cover_dest)
                cover_set = True
                log(f"  🖼  Cover set: {photo.name}")

        log(f"  ✅ {label}: {len(photos)} photos")

    # Write manifest
    manifest_path = export_dir / "INDEX.txt"
    manifest_lines += [
        "",
        "=" * 60,
        f"Total photos: {total}",
        "",
        "Print service suggestions:",
        "  • Artifact Uprising  — artifactuprising.com",
        "  • Chatbooks          — chatbooks.com",
        "  • Printique          — printique.com",
        "",
        "McGee Family · Faith. Family. Forever.",
    ]
    manifest_path.write_text("\n".join(manifest_lines))

    return export_dir


def main():
    args = sys.argv[1:]
    current_year = str(datetime.now().year)

    if not args:
        target = current_year
    elif args[0] == "all":
        target = "all"
    else:
        target = args[0]

    log(f"🌲 McGee Family Photo Book Export")
    log(f"   Source: {PHOTOS_DIR}")

    if target == "all":
        out = export_year("All-Years")
    else:
        out = export_year(target)

    print()
    log(f"🎉 Done! {out}")
    log(f"   Open in Finder: open '{out}'")
    os.system(f"open '{out}'")


if __name__ == "__main__":
    main()
