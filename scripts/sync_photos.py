#!/usr/bin/env python3
"""
McGee Family Website — iCloud Photo Sync Script
================================================
Syncs photos from iCloud Drive → site repo → GitHub Pages

Run manually:  python3 scripts/sync_photos.py
Run on schedule via macOS Shortcut or launchd (see README)

What it does:
  1. Reads each subfolder in iCloud Drive/McGee Website/Website Photos/
  2. Compares against photos/  in the site repo
  3. Copies new photos in (shutil.copy2 only — NO sips, NO compression)
  4. Removes photos deleted from iCloud
  5. Rebuilds gallery.html with correct tabs and photo lists
  6. Commits and pushes to GitHub automatically

RULES:
  - Never use sips — it corrupts photos to black. Raw copy only.
  - All photo extensions must be lowercase (.jpg / .jpeg) — GitHub Pages is case-sensitive.
  - HEIC files are skipped (export from Photos as JPEG before adding to iCloud folder).
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────

ICLOUD_SRC = Path("/Users/benjamin_mcgee/Library/Mobile Documents/com~apple~CloudDocs/McGee Website/Website Photos")
SITE_ROOT  = Path("/Users/benjamin_mcgee/Documents/Enchanté/Conversations/4A2C3E4D-5130-4C0E-ACB6-B12ED50E5737/mcgee-family")
PHOTOS_DIR = SITE_ROOT / "photos"

# Maps iCloud folder name → (site subfolder, gallery tab label)
# NOTE: "Family Photoshoot_Baby McGee Annoucement June - 2026" maps to baby-mcgee,
#       NOT to family. The real family photos live in the "Family" iCloud folder.
FOLDER_MAP = {
    "Family":                                               ("family",        "👨‍👩‍👦 Family"),
    "Weddding Photo's":                                     ("wedding",        "💍 Wedding"),
    "Engagement":                                           ("engagement",     "💍 Engagement"),
    "Honeymoon":                                            ("honeymoon",      "🌏 Honeymoon"),
    "Levi":                                                 ("levi",           "🧒 Levi"),
    "Levi 7th Golden Birthday":                             ("levi-birthday",  "🎂 Levi's 7th"),
    "Phoenix":                                              ("phoenix",        "🐕 Phoenix"),
    "Bentley":                                              ("bentley",        "🐾 Bentley"),
    # Both of these iCloud folders feed into baby-mcgee/
    "Baby McGee":                                           ("baby-mcgee",    "🌿 Baby McGee"),
    "Family Photoshoot_Baby McGee Annoucement June - 2026": ("baby-mcgee",    "🌿 Baby McGee"),
}

# Only copy still-image formats. Skip MOV, MP4, HEIC.
PHOTO_EXTS = {".jpg", ".jpeg", ".png"}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd or SITE_ROOT,
                            capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(f"  ⚠️  {result.stderr.strip()}")
    return result.stdout.strip()

def is_photo(path: Path) -> bool:
    return path.suffix.lower() in PHOTO_EXTS and not path.name.startswith(".")

# ── STEP 1: SYNC PHOTOS ───────────────────────────────────────────────────────

def sync_photos():
    added   = []
    removed = []
    changes = False

    # Track which site folders have been seeded so we don't double-remove
    # when two iCloud folders map to the same dest (e.g. baby-mcgee).
    # Build a unified src set per dest folder first.
    dest_to_src: dict[str, set] = {}
    for icloud_folder, (site_folder, _) in FOLDER_MAP.items():
        src_dir = ICLOUD_SRC / icloud_folder
        if not src_dir.exists():
            continue
        if site_folder not in dest_to_src:
            dest_to_src[site_folder] = set()
        for f in src_dir.iterdir():
            if is_photo(f):
                # Normalize to lowercase extension
                dest_to_src[site_folder].add(f.stem + f.suffix.lower())

    processed_dest = set()

    for icloud_folder, (site_folder, label) in FOLDER_MAP.items():
        src_dir  = ICLOUD_SRC / icloud_folder
        dest_dir = PHOTOS_DIR / site_folder

        if not src_dir.exists():
            log(f"⏭  iCloud folder not found, skipping: {icloud_folder}")
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Photos in this specific iCloud source folder
        for f in sorted(src_dir.iterdir()):
            if not is_photo(f):
                continue
            new_name  = f.stem + f.suffix.lower()   # enforce lowercase ext
            dest_path = dest_dir / new_name
            if not dest_path.exists():
                shutil.copy2(f, dest_path)           # raw copy — NO sips
                added.append(f"{site_folder}/{new_name}")
                changes = True

        # Remove orphaned files — only once per dest folder
        if site_folder not in processed_dest:
            processed_dest.add(site_folder)
            unified_src = dest_to_src.get(site_folder, set())
            for dest_file in list(dest_dir.iterdir()):
                if is_photo(dest_file) and dest_file.name not in unified_src:
                    dest_file.unlink()
                    removed.append(f"{site_folder}/{dest_file.name}")
                    changes = True

    if added:
        log(f"➕ Added   {len(added)} photo(s): {', '.join(added[:5])}{'...' if len(added) > 5 else ''}")
    if removed:
        log(f"➖ Removed {len(removed)} photo(s): {', '.join(removed[:5])}{'...' if len(removed) > 5 else ''}")
    if not added and not removed:
        log("✅ Photos already in sync — no changes needed")

    return changes

# ── STEP 2: REBUILD GALLERY.HTML ─────────────────────────────────────────────

def rebuild_gallery():
    gallery_path = SITE_ROOT / "gallery.html"

    def img_tags(alt, subdir):
        d = PHOTOS_DIR / subdir
        if not d.exists():
            return ""
        files = sorted([f.name for f in d.iterdir() if is_photo(f)])
        return "\n".join(
            f'        <img src="photos/{subdir}/{f}" alt="{alt}" loading="lazy"/>'
            for f in files
        )

    with open(gallery_path, "r") as f:
        html = f.read()

    section_map = {
        "gallery-family":        ("McGee Family",  "family"),
        "gallery-wedding":       ("Wedding",        "wedding"),
        "gallery-engagement":    ("Engagement",     "engagement"),
        "gallery-honeymoon":     ("Thailand",       "honeymoon"),
        "gallery-levi":          ("Levi",           "levi"),
        "gallery-levi-birthday": ("Levi Birthday",  "levi-birthday"),
        "gallery-phoenix":       ("Phoenix",        "phoenix"),
        "gallery-bentley":       ("Bentley",        "bentley"),
        "gallery-baby-mcgee":    ("Baby McGee",     "baby-mcgee"),
    }

    for section_id, (alt, subdir) in section_map.items():
        new_imgs = img_tags(alt, subdir)
        pattern = (
            rf'(id="{section_id}".*?<div class="masonry">)'
            rf'(.*?)'
            rf'(</div>\s*</div>\s*(?:<div class="gallery-section"|</div>\s*</div>\s*<footer))'
        )
        def replacer(m, imgs=new_imgs):
            return m.group(1) + "\n" + imgs + "\n      " + m.group(3)
        html = re.sub(pattern, replacer, html, flags=re.DOTALL)

    with open(gallery_path, "w") as f:
        f.write(html)

    log("✅ gallery.html rebuilt")

# ── STEP 3: GIT COMMIT & PUSH ─────────────────────────────────────────────────

def git_sync():
    log("📦 Staging changes...")
    run("git add photos/ gallery.html")

    status = run("git status --short")
    if not status:
        log("✅ Nothing new to commit")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    run(f'git commit -m "Auto-sync photos from iCloud Drive — {timestamp}"')
    log("🚀 Pushing to GitHub...")
    run("git push")
    log("✅ Pushed — site will update in ~60 seconds")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    log("🌲 McGee Family Photo Sync — Starting")
    log(f"   iCloud source: {ICLOUD_SRC}")
    log(f"   Site root:     {SITE_ROOT}")
    print()

    log("Step 1/3 — Syncing photos from iCloud Drive...")
    changes = sync_photos()
    print()

    log("Step 2/3 — Rebuilding gallery.html...")
    rebuild_gallery()
    print()

    log("Step 3/3 — Committing and pushing to GitHub...")
    git_sync()
    print()

    log("🎉 Done!")

if __name__ == "__main__":
    main()
