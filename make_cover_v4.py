"""Podcast cover v4 - flat "sticker" style after blush.design's Broccoli Book
Club example: solid vivid ground, one witty object (a book wearing
headphones), thick outlines, title integrated on the object.

Run:  .venv/bin/python make_cover_v4.py [out.jpg]
"""
import sys

from PIL import Image, ImageDraw, ImageFont

S = 3000
BG = (255, 205, 0)          # vivid yellow
BOOK = (16, 56, 84)         # deep ink blue
PAGES = (255, 253, 245)     # paper white
CUSHION = (255, 75, 62)     # warm red
LINE = (12, 12, 14)         # near-black outline
OW = 30                     # outline width

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

# --- the object, drawn upright on its own layer then tilted ------------
layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(layer)

cx = S // 2
bw, bh = int(S * 0.46), int(S * 0.56)
bx0, by0 = cx - bw // 2, int(S * 0.30)
bx1, by1 = bx0 + bw, by0 + bh
r = int(S * 0.028)

# page block peeking out right + bottom
d.rounded_rectangle([bx0 + 60, by0 + 60, bx1 + 70, by1 + 70],
                    radius=r, fill=PAGES, outline=LINE, width=OW)
# cover
d.rounded_rectangle([bx0, by0, bx1, by1],
                    radius=r, fill=BOOK, outline=LINE, width=OW)

# earcups hug the book's sides; the band arc lands exactly on their tops
cup_y = by0 + int(bh * 0.18)                 # cushion centre height
cup_hw, cup_hh = int(S * 0.042), int(S * 0.085)   # vertical pill halves
band_r = (bw // 2) + cup_hw                  # so arc ends at cup centres

# band first (cups drawn over its ends)
d.arc([cx - band_r, cup_y - band_r, cx + band_r, cup_y + band_r],
      start=180, end=360, fill=LINE, width=int(S * 0.032))

for side in (-1, 1):
    ex = cx + side * band_r
    cup = [ex - cup_hw, cup_y - cup_hh, ex + cup_hw, cup_y + cup_hh]
    d.rounded_rectangle(cup, radius=cup_hw, fill=CUSHION, outline=LINE, width=OW)
    pad_x, pad_y = int(cup_hw * 0.45), int(cup_hh * 0.30)
    d.rounded_rectangle([cup[0] + pad_x, cup[1] + pad_y,
                         cup[2] - pad_x, cup[3] - pad_y],
                        radius=cup_hw, fill=LINE)

# sound arcs radiating from each earcup
for side in (-1, 1):
    ex = cx + side * (band_r + cup_hw + int(S * 0.018))
    for rr in (int(S * 0.045), int(S * 0.075), int(S * 0.105)):
        start, end = (150, 210) if side < 0 else (-30, 30)
        d.arc([ex - rr, cup_y - rr, ex + rr, cup_y + rr],
              start=start, end=end, fill=LINE, width=int(S * 0.013))

# title on the cover, like a book title
font = load_face(int(S * 0.125))
ty = by0 + int(bh * 0.40)
for word, yy in (("READ", ty), ("ALOUD", ty + int(S * 0.145))):
    d.text((cx, yy), word, font=font, anchor="mm",
           fill=PAGES, stroke_width=int(OW * 0.6), stroke_fill=LINE)

layer = layer.rotate(-7, resample=Image.BICUBIC, center=(cx, S // 2))
img.paste(layer, (0, 0), layer)

# --- tiny strap, bottom right (like the reference's logo corner) --------
d2 = ImageDraw.Draw(img)
small = load_face(int(S * 0.030))
d2.text((int(S * 0.94), int(S * 0.94)), "LU'S PRIVATE FEED",
        font=small, anchor="rm", fill=LINE)

out = sys.argv[1] if len(sys.argv) > 1 else "cover_v4.jpg"
img.save(out, quality=92)
print(f"wrote {out}")
