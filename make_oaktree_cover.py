"""Podcast cover for "Howard Marks Memos" - sibling to make_berkshire_cover.py
(same letter-sheet + headphones template) but its own identity: deep oxblood
ground, gold acorn emblem, serif title.

Run:  .venv/bin/python make_oaktree_cover.py [out.jpg]
"""
import sys

from PIL import Image, ImageDraw, ImageFont

S = 3000
BG = (74, 26, 30)           # deep oxblood
SHEET = (247, 240, 224)     # warm cream paper
INK = (26, 18, 16)          # near-black outline
CUSHION = (74, 26, 30)      # earcups pick up the ground
GOLD = (196, 152, 58)       # acorn / accent gold
OW = 30

SERIF = [
    ("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", None),
    ("/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf", None),
    ("/System/Library/Fonts/NewYork.ttf", None),
    ("/System/Library/Fonts/Georgia.ttf", None),
]
SERIF_REG = [
    ("/System/Library/Fonts/Supplemental/Georgia.ttf", None),
    ("/System/Library/Fonts/Supplemental/Times New Roman.ttf", None),
]


def _load(faces, size):
    for path, want in faces:
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa
            continue
    return ImageFont.load_default()


def _fit(faces, text, max_w, start):
    size = start
    while size > 24:
        f = _load(faces, size)
        if f.getbbox(text)[2] - f.getbbox(text)[0] <= max_w:
            return f
        size -= 8
    return _load(faces, size)


img = Image.new("RGB", (S, S), BG)
layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(layer)

cx = S // 2
sw, sh = int(S * 0.52), int(S * 0.62)
sx0, sy0 = cx - sw // 2, int(S * 0.28)
sx1, sy1 = sx0 + sw, sy0 + sh
r = int(S * 0.022)

d.rounded_rectangle([sx0 + 55, sy0 + 55, sx1 + 60, sy1 + 60],
                    radius=r, fill=(236, 228, 208), outline=INK, width=OW)
d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=r, fill=SHEET,
                    outline=INK, width=OW)

# headphones
cup_y = sy0 + int(sh * 0.16)
cup_hw, cup_hh = int(S * 0.040), int(S * 0.082)
band_r = (sw // 2) + cup_hw
d.arc([cx - band_r, cup_y - band_r, cx + band_r, cup_y + band_r],
      start=180, end=360, fill=INK, width=int(S * 0.030))
for side in (-1, 1):
    ex = cx + side * band_r
    cup = [ex - cup_hw, cup_y - cup_hh, ex + cup_hw, cup_y + cup_hh]
    d.rounded_rectangle(cup, radius=cup_hw, fill=CUSHION, outline=INK, width=OW)
    px, py = int(cup_hw * 0.45), int(cup_hh * 0.30)
    d.rounded_rectangle([cup[0] + px, cup[1] + py, cup[2] - px, cup[3] - py],
                        radius=cup_hw, fill=INK)

# title
tcx = cx
inner_w = int(sw * 0.80)
kicker = _load(SERIF_REG, int(S * 0.050))
d.text((tcx, sy0 + int(sh * 0.29)), "HOWARD MARKS", font=kicker, anchor="mm", fill=INK)
big = _fit(SERIF, "OAKTREE", inner_w, int(S * 0.108))
d.text((tcx, sy0 + int(sh * 0.42)), "OAKTREE", font=big, anchor="mm", fill=INK)
big2 = _fit(SERIF, "MEMOS", inner_w, int(S * 0.108))
d.text((tcx, sy0 + int(sh * 0.55)), "MEMOS", font=big2, anchor="mm", fill=INK)

ry = sy0 + int(sh * 0.64)
d.line([tcx - int(sw * 0.24), ry, tcx + int(sw * 0.24), ry], fill=INK, width=8)
yrs = _load(SERIF, int(S * 0.052))
d.text((tcx, sy0 + int(sh * 0.72)), "1990 - 2025", font=yrs, anchor="mm", fill=GOLD)

# gold acorn emblem, bottom-centre of the sheet
acx, acy = tcx, sy1 - int(sh * 0.13)
nut_w, nut_h = int(S * 0.052), int(S * 0.060)
# cap
d.pieslice([acx - nut_w, acy - int(nut_h * 0.95), acx + nut_w, acy + int(nut_h * 0.15)],
           start=180, end=360, fill=GOLD, outline=INK, width=int(OW * 0.6))
d.line([acx, acy - nut_h, acx, acy - int(nut_h * 1.18)], fill=INK, width=int(OW * 0.7))
# nut (raised to meet the cap's flat underside)
d.ellipse([acx - int(nut_w * 0.82), acy - int(nut_h * 0.42),
           acx + int(nut_w * 0.82), acy + int(nut_h * 0.66)],
          fill=GOLD, outline=INK, width=int(OW * 0.6))

layer = layer.rotate(-5, resample=Image.BICUBIC, center=(cx, S // 2))
img.paste(layer, (0, 0), layer)

d2 = ImageDraw.Draw(img)
small = _load(SERIF_REG, int(S * 0.028))
d2.text((int(S * 0.95), int(S * 0.955)), "read aloud  -  private feed",
        font=small, anchor="rm", fill=(226, 214, 210))

out = sys.argv[1] if len(sys.argv) > 1 else "oaktree_cover.jpg"
img.resize((1500, 1500), Image.LANCZOS).save(out, quality=90)
print(f"wrote {out}")
