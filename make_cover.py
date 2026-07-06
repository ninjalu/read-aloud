"""Generate the podcast cover art (3000x3000 JPEG) for the private feed.

Dark, typographic, a waveform cutting through the title with a chromatic
glitch echo. Run:  .venv/bin/python make_cover.py [out.jpg]
"""
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

S = 3000
BG = (11, 11, 14)          # near-black
INK = (244, 241, 232)      # bone white
ACID = (217, 255, 59)      # acid yellow-green
RED = (255, 46, 60)        # hot red
CYAN = (57, 210, 255)      # electric cyan

FACES = [
    ("/System/Library/Fonts/HelveticaNeue.ttc", "Condensed Black"),
    ("/System/Library/Fonts/Avenir Next Condensed.ttc", "Heavy"),
    ("/System/Library/Fonts/Supplemental/Arial Black.ttf", None),
]


def load_face(size: int) -> ImageFont.FreeTypeFont:
    for path, want in FACES:
        for idx in range(14):
            try:
                f = ImageFont.truetype(path, size, index=idx)
            except Exception:  # noqa
                break
            if want is None or want.lower() in " ".join(f.getname()).lower():
                return f
    return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)


img = Image.new("RGB", (S, S), BG)
draw = ImageDraw.Draw(img, "RGBA")

# --- waveform band across the middle, behind the type -----------------
random.seed(7)
mid = S // 2
bar_w, gap = 26, 18
x = 0
i = 0
while x < S:
    cluster = abs(np.sin(i * 0.31)) * abs(np.sin(i * 0.077 + 1.2))
    h = int(S * 0.02 + S * 0.30 * cluster * random.uniform(0.55, 1.0))
    draw.rounded_rectangle([x, mid - h, x + bar_w, mid + h],
                           radius=bar_w // 2, fill=ACID + (255,))
    x += bar_w + gap
    i += 1

# --- title: READ / ALOUD stacked, glitch echoes then ink --------------
font = load_face(int(S * 0.315))
y_read, y_aloud = int(S * 0.335), int(S * 0.635)

for word, y in (("READ", y_read), ("ALOUD", y_aloud)):
    for dx, dy, col, a in ((-26, -14, CYAN, 160), (26, 14, RED, 160)):
        draw.text((S // 2 + dx, y + dy), word, font=font,
                  anchor="mm", fill=col + (a,))
    draw.text((S // 2, y), word, font=font, anchor="mm", fill=INK)

# --- footer strap ------------------------------------------------------
small = load_face(int(S * 0.036))
strap = "L U ' S   P R I V A T E   F E E D"
draw.text((S // 2, int(S * 0.895)), strap, font=small, anchor="mm", fill=ACID)

# thin frame
inset = int(S * 0.02)
draw.rectangle([inset, inset, S - inset, S - inset],
               outline=INK + (60,), width=6)

# --- film grain --------------------------------------------------------
rng = np.random.default_rng(7)
noise = rng.normal(0, 11, (S, S, 1)).repeat(3, axis=2)
arr = np.clip(np.asarray(img).astype(np.int16) + noise.astype(np.int16), 0, 255)
img = Image.fromarray(arr.astype(np.uint8))

out = sys.argv[1] if len(sys.argv) > 1 else "cover_edgy.jpg"
img.save(out, quality=90)
print(f"wrote {out}")
