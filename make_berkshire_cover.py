"""Podcast cover for "Warren Buffett's Letters" - flat sticker style, sibling to
make_cover_v4.py but its own identity: a cream letter sheet on Berkshire green,
headphones over the top, a gold seal, serif title.

Run:  .venv/bin/python make_berkshire_cover.py [out.jpg]
"""
import sys

from PIL import Image, ImageDraw, ImageFont

S = 3000
BG = (14, 61, 46)           # deep Berkshire green
SHEET = (247, 240, 224)     # warm cream paper
INK = (18, 24, 22)          # near-black outline
CUSHION = (18, 61, 46)      # earcups pick up the green ground
SEAL = (196, 152, 58)       # gold wax seal
RULE = (206, 194, 168)      # faint ruled lines on the sheet
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
            f = ImageFont.truetype(path, size)
            return f
        except Exception:  # noqa
            continue
    return ImageFont.load_default()


def _fit(faces, text, max_w, start):
    """Largest font (<= start px) whose rendered `text` width fits max_w."""
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

# a second sheet peeking behind (a stack of letters)
d.rounded_rectangle([sx0 + 55, sy0 + 55, sx1 + 60, sy1 + 60],
                    radius=r, fill=(236, 228, 208), outline=INK, width=OW)
# front sheet
d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=r, fill=SHEET,
                    outline=INK, width=INK and OW)

# headphones hugging the sheet
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

# title, set like a letterhead - auto-fit the big words inside the sheet
tcx = cx
inner_w = int(sw * 0.80)                       # keep clear of the sheet edges
kicker = _load(SERIF_REG, int(S * 0.050))
d.text((tcx, sy0 + int(sh * 0.30)), "THE", font=kicker, anchor="mm", fill=INK)
big = _fit(SERIF, "BERKSHIRE", inner_w, int(S * 0.100))
d.text((tcx, sy0 + int(sh * 0.42)), "BERKSHIRE", font=big, anchor="mm", fill=INK)
big2 = _fit(SERIF, "LETTERS", inner_w, int(S * 0.100))
d.text((tcx, sy0 + int(sh * 0.55)), "LETTERS", font=big2, anchor="mm", fill=INK)

# thin rule + byline
ry = sy0 + int(sh * 0.64)
d.line([tcx - int(sw * 0.28), ry, tcx + int(sw * 0.28), ry], fill=INK, width=8)
by = _load(SERIF_REG, int(S * 0.044))
d.text((tcx, sy0 + int(sh * 0.71)), "WARREN BUFFETT", font=by, anchor="mm", fill=INK)
yrs = _load(SERIF, int(S * 0.050))
d.text((tcx, sy0 + int(sh * 0.79)), "1977 - 2024", font=yrs, anchor="mm", fill=SEAL)

# gold wax seal, bottom-right of the sheet
seal_r = int(S * 0.055)
scx, scy = sx1 - int(sw * 0.16), sy1 - int(sh * 0.13)
d.ellipse([scx - seal_r, scy - seal_r, scx + seal_r, scy + seal_r],
          fill=SEAL, outline=INK, width=int(OW * 0.7))
wb = _load(SERIF, int(seal_r * 1.05))
d.text((scx, scy - int(seal_r * 0.04)), "WB", font=wb, anchor="mm", fill=(60, 40, 10))

layer = layer.rotate(-5, resample=Image.BICUBIC, center=(cx, S // 2))
img.paste(layer, (0, 0), layer)

# strap, bottom-right corner
d2 = ImageDraw.Draw(img)
small = _load(SERIF_REG, int(S * 0.028))
d2.text((int(S * 0.95), int(S * 0.955)), "read aloud  -  private feed",
        font=small, anchor="rm", fill=(226, 222, 210))

out = sys.argv[1] if len(sys.argv) > 1 else "berkshire_cover.jpg"
# Apple wants 1400-3000px square; downscale the 3000 render for a crisp JPEG.
img.resize((1500, 1500), Image.LANCZOS).save(out, quality=90)
print(f"wrote {out}")
