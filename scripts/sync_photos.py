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
  3. Copies new photos in, removes deleted ones
  4. Converts HEIC to JPEG if needed
  5. Rebuilds gallery.html with correct tabs and photo lists
  6. Commits and pushes to GitHub automatically
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

# Maps iCloud folder name → site subfolder name → gallery tab label
FOLDER_MAP = {
    "Family Photoshoot_Baby McGee Annoucement June - 2026": ("family",        "👨‍👩‍👦 Family"),
    "Weddding Photo's":                                     ("wedding",        "💍 Wedding"),
    "Engagement":                                           ("engagement",     "💍 Engagement"),
    "Honeymoon":                                            ("honeymoon",      "🌏 Honeymoon"),
    "Levi":                                                 ("levi",           "🧒 Levi"),
    "Levi 7th Golden Birthday":                             ("levi-birthday",  "🎂 Levi's 7th"),
    "Brittney":                                             ("brittney",       "👩 Brittney"),
    "Ben":                                                  ("ben",            "👨 Ben"),
    "Phoenix":                                              ("phoenix",        "🐕 Phoenix"),
    "Bentley":                                              ("bentley",        "🐾 Bentley"),
    "Baby McGee":                                           ("baby-mcgee",     "🌿 Baby McGee"),
}

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".JPG", ".JPEG", ".PNG", ".HEIC"}

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
    return path.suffix in PHOTO_EXTS and not path.name.startswith(".")

def convert_heic(src: Path, dst_dir: Path) -> Path:
    """Convert HEIC to JPEG using sips (built into macOS). Returns new path."""
    dst = dst_dir / (src.stem + ".jpeg")
    result = subprocess.run(
        ["sips", "-s", "format", "jpeg", str(src), "--out", str(dst)],
        capture_output=True
    )
    if result.returncode == 0 and dst.exists():
        compress_photo(dst)
        return dst
    return None

def compress_photo(path: Path):
    """Compress a JPEG in-place to max 1400px wide at quality 72. Safe for web."""
    size_before = path.stat().st_size
    if size_before < 512_000:
        return  # Already small enough
    subprocess.run(
        ["sips", "-Z", "1400", "-s", "format", "jpeg", "-s", "formatOptions", "72",
         str(path), "--out", str(path)],
        capture_output=True
    )
    size_after = path.stat().st_size
    saved = (size_before - size_after) // 1024
    if saved > 0:
        log(f"  🗜 Compressed {path.name}: {size_before//1024}KB → {size_after//1024}KB (saved {saved}KB)")

# ── STEP 1: SYNC PHOTOS ───────────────────────────────────────────────────────

def sync_photos():
    added   = []
    removed = []
    skipped = []
    changes = False

    for icloud_folder, (site_folder, label) in FOLDER_MAP.items():
        src_dir  = ICLOUD_SRC / icloud_folder
        dest_dir = PHOTOS_DIR / site_folder

        if not src_dir.exists():
            log(f"⏭  iCloud folder not found, skipping: {icloud_folder}")
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Photos currently in iCloud folder
        src_photos = {}
        for f in src_dir.iterdir():
            if is_photo(f):
                # Normalize HEIC name for comparison
                key = f.stem + (".jpeg" if f.suffix.lower() == ".heic" else f.suffix)
                src_photos[key] = f

        # Photos currently in site folder
        dest_photos = {f.name for f in dest_dir.iterdir() if is_photo(f)}

        # --- ADD new photos ---
        for name, src_path in src_photos.items():
            if name not in dest_photos:
                if src_path.suffix.lower() == ".heic":
                    converted = convert_heic(src_path, dest_dir)
                    if converted:
                        added.append(f"{site_folder}/{converted.name}")
                        changes = True
                    else:
                        log(f"  ❌ HEIC conversion failed: {src_path.name}")
                else:
                    dest_path = dest_dir / name
                    shutil.copy2(src_path, dest_path)
                    compress_photo(dest_path)
                    added.append(f"{site_folder}/{name}")
                    changes = True

        # --- REMOVE deleted photos ---
        for dest_name in list(dest_photos):
            if dest_name not in src_photos:
                (dest_dir / dest_name).unlink()
                removed.append(f"{site_folder}/{dest_name}")
                changes = True

    if added:
        log(f"➕ Added   {len(added)} photo(s): {', '.join(added[:5])}{'...' if len(added)>5 else ''}")
    if removed:
        log(f"➖ Removed {len(removed)} photo(s): {', '.join(removed[:5])}{'...' if len(removed)>5 else ''}")
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

    # Rebuild each gallery section
    section_map = {
        "gallery-family":       ("McGee Family",  "family"),
        "gallery-wedding":      ("Wedding",        "wedding"),
        "gallery-engagement":   ("Engagement",     "engagement"),
        "gallery-honeymoon":    ("Thailand",       "honeymoon"),
        "gallery-levi":         ("Levi",           "levi"),
        "gallery-levi-birthday":("Levi Birthday",  "levi-birthday"),
        "gallery-brittney":     ("Brittney",       "brittney"),
        "gallery-phoenix":      ("Phoenix",        "phoenix"),
        "gallery-bentley":      ("Bentley",        "bentley"),
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
    result = run("git push")
    log("✅ Pushed — site will update in ~60 seconds")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    log("🌲 McGee Family Photo Sync — Starting")
    log(f"   iCloud source: {ICLOUD_SRC}")
    log(f"   Site root:     {SITE_ROOT}")
    print()

    # Step 1 — Sync photos
    log("Step 1/3 — Syncing photos from iCloud Drive...")
    changes = sync_photos()
    print()

    # Step 2 — Rebuild gallery (always, to catch any drift)
    log("Step 2/3 — Rebuilding gallery.html...")
    rebuild_gallery()
    print()

    # Step 3 — Commit and push
    log("Step 3/3 — Committing and pushing to GitHub...")
    git_sync()
    print()

    log("🎉 Done!")

if __name__ == "__main__":
    main()
