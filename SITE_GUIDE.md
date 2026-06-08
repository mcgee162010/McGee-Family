# McGee Family Website — Site Maintenance Guide
**mcgeefamily2025.com** · Last updated June 2026

---

## The Simple Version

You never need to touch code for the most common tasks.
Just tell Enchanté what you want and it handles everything.

**Common requests:**
- "Add these photos to the gallery"
- "Write a new update post about [thing]"
- "Update the baby shower time"
- "Baby McGee arrived — name is [X], it's a [boy/girl], born [date]"
- "Add a new event to the events page"
- "Fix the spelling on [page]"

---

## Site Structure

```
mcgeefamily2025.com/
├── index.html          ← Home page
├── family.html         ← Our Family
├── our-story.html      ← How we met, proposal, wedding
├── gallery.html        ← All photo galleries
├── events.html         ← Events hub
├── baby-shower.html    ← Baby shower RSVP + registry + poll
├── updates.html        ← Life updates / journal
├── timeline.html       ← Full family timeline
├── letters.html        ← Letters to Levi + Baby McGee
├── year-in-review.html ← Annual chapter (add one each December)
├── baby-mcgee.html     ← Arrival page (publish Sep 4 2026)
├── bentley.html        ← Bentley memorial
├── contact.html        ← Contact form
└── photos/
    ├── family/         ← Family photoshoot
    ├── wedding/        ← Wedding photos
    ├── honeymoon/      ← Thailand honeymoon
    ├── engagement/     ← Engagement photos
    ├── levi/           ← Levi's photos
    ├── levi-birthday/  ← Levi's 7th birthday
    ├── brittney/       ← Brittney's photos
    ├── phoenix/        ← Phoenix's photos
    ├── bentley/        ← Bentley's photos
    └── baby-mcgee/     ← Baby McGee photos
```

---

## Adding Photos

### Option 1 — iCloud (Recommended)
Drop photos into the correct subfolder:
```
iCloud Drive → McGee Website → Website Photos → [folder name]
```
The weekly sync runs every Sunday at 9 PM automatically.
To sync immediately: `python3 scripts/sync_photos.py`

### Option 2 — Ask Enchanté
"I updated the Levi photos folder — sync the site."

### Rules
- Photos auto-compress on sync — originals stay safe in iCloud
- Use `.jpeg` or `.jpg` extension — no `.HEIC` (auto-converted on sync)
- No sips compression — photos are copied raw

---

## Publishing Baby McGee's Arrival

When Baby McGee arrives, open Terminal and run:
```bash
bash "/Users/benjamin_mcgee/Documents/Enchanté/Conversations/4A2C3E4D-5130-4C0E-ACB6-B12ED50E5737/mcgee-family/scripts/publish_baby_mcgee.sh"
```

It will ask for: name, boy/girl, date, time, weight, length.
It updates the page and publishes automatically. Takes 2 minutes.

---

## Adding a Life Update Post

Tell Enchanté:
> "Add an update post — [title], [date], [what happened]"

Or copy this template into `updates.html` at the top of the posts list:

```html
<article class="post [post-milestone if it's a big moment]" data-category="[category]">
  <div class="post-header">
    <div class="post-icon" style="background:var(--sage-pale); border-left:4px solid var(--forest); ...">🌿</div>
    <div class="post-meta">
      <div class="post-date">[Date]</div>
      <div class="post-title">[Title]</div>
      <span class="post-category">[Category]</span>
    </div>
  </div>
  <div class="post-body">
    <p>[Content]</p>
  </div>
</article>
```

**Categories:** `baby-mcgee` · `family` · `levi` · `how-we-met` · `milestone`

---

## Adding an Event

1. Go to `events.html`
2. Copy an existing event card
3. Update: title, date, time, location, description, photo
4. Set `class="event-card"` for upcoming, `class="event-card past-card"` for past

---

## December Year in Review

Each December, open `year-in-review.html`:
1. Add a new year tab button: `<button class="year-tab" onclick="showYear('2027', this)">2027</button>`
2. Copy the 2026 section block
3. Change the year, update stats, swap photos, rewrite the letter
4. Save and push

---

## Pushing Changes to the Live Site

After any manual edit:
```bash
cd "/Users/benjamin_mcgee/Documents/Enchanté/Conversations/4A2C3E4D-5130-4C0E-ACB6-B12ED50E5737/mcgee-family"
git add .
git commit -m "Brief description of what changed"
git push
```
Site updates within 60–90 seconds.

---

## Key Services

| Service | What It Does | Login |
|---|---|---|
| **GitHub Pages** | Hosts the website | github.com/mcgee162010 |
| **Namecheap** | Owns mcgeefamily2025.com | namecheap.com |
| **Formspree** | Delivers RSVP + Contact emails | formspree.io (f/xpwzagna) |
| **JSONBin** | Stores live RSVP list + gender poll | jsonbin.io (Bin: 6a26fbd7...) |
| **iCloud Drive** | Photo source → syncs to site | Built into Mac |

---

## Color Palette (for reference)

| Name | Hex | Use |
|---|---|---|
| Forest | `#3D6B52` | Primary green, links, accents |
| Sage | `#7A9E7E` | Secondary green |
| Brown | `#6B4F3A` | Headings, footer background |
| Terracotta | `#C4714A` | CTAs, warm accents |
| Cream | `#FAF6EF` | Page background |

---

## If Something Breaks

1. Check GitHub Pages status: **Settings → Pages** in the repo
2. Hard refresh: `Cmd + Shift + R`
3. Open in private window: `Cmd + Shift + N`
4. Tell Enchanté: "Something is broken on [page] — [describe it]"

---

*Built with love in Queen Creek, Arizona · 2026*
*Faith. Family. Forever.*
