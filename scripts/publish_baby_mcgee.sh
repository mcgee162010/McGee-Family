#!/usr/bin/env bash
# ============================================================
# McGee Family Website — Baby McGee Arrival Publisher
# ============================================================
# Run this script the day Baby McGee arrives.
# Usage: bash scripts/publish_baby_mcgee.sh
#
# It will ask you for:
#   - Name
#   - Boy or girl
#   - Date, time, weight, length
# Then updates baby-mcgee.html, adds to the nav, and pushes.
# ============================================================

set -e

SITE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SITE"

echo ""
echo "🌿 McGee Family — Baby McGee Arrival Publisher"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Baby's name: " BABY_NAME
read -p "Boy or girl? (boy/girl): " GENDER
read -p "Birth date (e.g. September 4, 2026): " BIRTH_DATE
read -p "Birth time (e.g. 7:42 AM MST): " BIRTH_TIME
read -p "Weight (e.g. 7 lbs 3 oz): " WEIGHT
read -p "Length (e.g. 20 inches): " LENGTH

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Name:   $BABY_NAME"
echo "  Gender: $GENDER"
echo "  Date:   $BIRTH_DATE"
echo "  Time:   $BIRTH_TIME"
echo "  Weight: $WEIGHT"
echo "  Length: $LENGTH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Looks good? Publish now? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Cancelled."
  exit 0
fi

# Set gender-specific values
if [ "$GENDER" = "girl" ]; then
  GENDER_LABEL="a Girl"
  GENDER_EMOJI="🩷"
  REVEAL_COLOR="#BE185D"
  HERO_REVEAL="It's a Girl! 🩷"
else
  GENDER_LABEL="a Boy"
  GENDER_EMOJI="💙"
  REVEAL_COLOR="#1D4ED8"
  HERO_REVEAL="It's a Boy! 💙"
fi

echo "✏️  Updating baby-mcgee.html..."

python3 - <<PYEOF
import re

path = "$SITE/baby-mcgee.html"
with open(path, 'r') as f:
    html = f.read()

# Update hero headline
html = html.replace(
    '<span class="reveal" id="hero-reveal">is Here! 🌿</span>',
    '<span class="reveal" id="hero-reveal">$HERO_REVEAL</span>'
)

# Update hero subtitle
html = html.replace(
    'The McGees are officially a family of five. After nine months of anticipation, the sweetest little surprise has arrived — and the wait was absolutely worth it.',
    'The McGees are officially a family of five. $BABY_NAME arrived on $BIRTH_DATE — and the wait was absolutely worth it.'
)

# Update stat pills
html = html.replace('📅 Born: [Date]',    '📅 Born: $BIRTH_DATE')
html = html.replace('⏰ Time: [Time]',    '⏰ Time: $BIRTH_TIME')
html = html.replace('⚖️ Weight: [lbs oz]','⚖️ Weight: $WEIGHT')
html = html.replace('📏 Length: [inches]','📏 Length: $LENGTH')
html = html.replace('🌿 Name: [Baby\'s Name]', '🌿 Name: $BABY_NAME')

# Update gender reveal section
html = html.replace(
    'document.getElementById(\'reveal-answer\').style.color = \'var(--forest)\'',
    ''
)
html = html.replace(
    "It's a [Boy/Girl]! 🌿",
    "It's $GENDER_LABEL! $GENDER_EMOJI"
)
html = html.replace(
    'style="color:var(--forest);">It\'s a [Boy/Girl]! 🌿',
    'style="color:$REVEAL_COLOR;">It\'s $GENDER_LABEL! $GENDER_EMOJI'
)

# Update title
html = html.replace(
    '<title>Baby McGee is Here! · McGee Family</title>',
    '<title>$BABY_NAME is Here! · McGee Family</title>'
)

# Update footer
html = html.replace(
    'Ben · Brittney · Levi · Baby McGee · Phoenix · Queen Creek, AZ',
    'Ben · Brittney · Levi · $BABY_NAME · Phoenix · Queen Creek, AZ'
)

with open(path, 'w') as f:
    f.write(html)
print('✅ baby-mcgee.html updated')
PYEOF

echo "✏️  Adding Baby McGee to nav on all pages..."
python3 - <<PYEOF
import glob, re

SITE = "$SITE"
name = "$BABY_NAME"

for path in sorted(glob.glob(f"{SITE}/*.html")):
    with open(path) as f:
        html = f.read()
    # Add to nav after Contact
    old_contact = '      <li><a href="contact.html">Contact</a></li>\n    </ul>'
    new_contact = f'      <li><a href="contact.html">Contact</a></li>\n      <li><a href="baby-mcgee.html">🌿 {name}</a></li>\n    </ul>'
    if old_contact in html and 'baby-mcgee.html' not in html:
        html = html.replace(old_contact, new_contact)
        with open(path, 'w') as f:
            f.write(html)
        print(f'  ✅ {path.split("/")[-1]}')
PYEOF

echo ""
echo "📦 Committing and pushing..."
git add .
git commit -m "🌿 $BABY_NAME has arrived! — $BIRTH_DATE, $WEIGHT, $LENGTH"
git push

echo ""
echo "🎉 Done! The world knows $BABY_NAME is here."
echo "   Visit: https://mcgeefamily2025.com/baby-mcgee.html"
echo ""
