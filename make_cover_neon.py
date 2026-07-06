"""Generate the NEON podcast cover (3000x3000 JPEG) - glowing tube-sign type,
hue-shifting waveform, scanlines, film grain.

Run:  .venv/bin/python make_cover_neon.py [out.jpg]
"""
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 3000
BG = (8, 5, 20)             # deep violet-black
CYAN = (0, 240, 255)
BLUE = (43, 107, 255)
MAGENTA = (255, 43, 214)
ORANGE = (255, 158, 0)
VIOLET = (122, 43, 255)

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


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def vgrad(w, h, top, bottom):
    """Vertical gradient RGB image."""
    col = np.linspace(np.array(top), np.array(bottom), h)
    return Image.fromarray(np.tile(col[:, None, :], (1, w, 1)).astype(np.uint8))


def glow(layer: Image.Image, radius: int, strength: float = 1.0) -> Image.Image:
    """Blurred, brightened copy of an RGBA layer for neon bloom."""
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        a = g.getchannel("A").point(lambda v: min(255, int(v * strength)))
        g.putalpha(a)
    return g


img = Image.new("RGB", (S, S), BG)

# --- ambient bloom: violet centre, magenta corners --------------------
yy, xx = np.mgrid[0:S, 0:S]
d = np.sqrt((xx - S / 2) ** 2 + (yy - S / 2) ** 2) / (S * 0.72)
bloom = np.clip(1 - d, 0, 1) ** 2.2
amb = np.zeros((S, S, 3))
for ch in range(3):
    amb[:, :, ch] = bloom * VIOLET[ch] * 0.30
img = Image.fromarray(np.clip(np.asarray(img) + amb, 0, 255).astype(np.uint8))

# --- waveform: neon tubes, hue shifting cyan -> magenta -> orange ------
wave = Image.new("RGBA", (S, S), (0, 0, 0, 0))
wd = ImageDraw.Draw(wave)
random.seed(11)
mid = S // 2
bar_w, gap = 24, 20
x, i = 0, 0
while x < S:
    t = x / S
    col = lerp(CYAN, MAGENTA, t * 2) if t < 0.5 else lerp(MAGENTA, ORANGE, (t - 0.5) * 2)
    cluster = abs(np.sin(i * 0.31)) * abs(np.sin(i * 0.077 + 1.2))
    h = int(S * 0.02 + S * 0.31 * cluster * random.uniform(0.55, 1.0))
    wd.rounded_rectangle([x, mid - h, x + bar_w, mid + h],
                         radius=bar_w // 2, fill=col + (255,))
    x += bar_w + gap
    i += 1

base = img.convert("RGBA")
base.alpha_composite(glow(wave, 70, 1.6))     # wide soft bloom
base.alpha_composite(glow(wave, 18, 1.2))     # tight hot bloom
base.alpha_composite(wave)                    # crisp tube core

# --- title: gradient-filled words with tube glow -----------------------
font = load_face(int(S * 0.315))
words = (("READ", int(S * 0.335), CYAN, BLUE),
         ("ALOUD", int(S * 0.635), MAGENTA, ORANGE))

def text_mask(word: str, y: int, stroke: int = 0) -> Image.Image:
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).text((S // 2, y), word, font=font, anchor="mm",
                           fill=255, stroke_width=stroke, stroke_fill=255)
    return m


for word, y, top, bottom in words:
    from PIL import ImageChops
    plain = text_mask(word, y)
    ring = ImageChops.subtract(text_mask(word, y, stroke=30), plain)  # tube outline
    filament = ImageChops.subtract(text_mask(word, y, stroke=8), plain)

    # dark "unlit glass" interior so letters block the waveform and read solid
    interior = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    interior.paste(vgrad(S, S, tuple(int(c * 0.16) for c in top),
                         tuple(int(c * 0.16) for c in bottom)), (0, 0), plain)
    base.alpha_composite(interior)

    # vivid gradient tube + bloom
    tube = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tube.paste(vgrad(S, S, top, bottom), (0, 0), ring)
    base.alpha_composite(glow(tube, 90, 1.6))    # halo
    base.alpha_composite(glow(tube, 20, 1.4))    # hot edge
    base.alpha_composite(tube)                   # crisp tube

    # white filament hugging the inside of the tube
    fil = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fil.paste(Image.new("RGB", (S, S), (255, 255, 255)), (0, 0),
              filament.point(lambda v: int(v * 0.85)))
    base.alpha_composite(fil.filter(ImageFilter.GaussianBlur(3)))

# --- strap -------------------------------------------------------------
small = load_face(int(S * 0.036))
strapl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(strapl).text((S // 2, int(S * 0.895)),
                            "L U ' S   P R I V A T E   F E E D",
                            font=small, anchor="mm", fill=CYAN + (255,))
base.alpha_composite(glow(strapl, 26, 1.5))
base.alpha_composite(strapl)

# --- neon frame ---------------------------------------------------------
framel = Image.new("RGBA", (S, S), (0, 0, 0, 0))
inset = int(S * 0.022)
ImageDraw.Draw(framel).rounded_rectangle(
    [inset, inset, S - inset, S - inset], radius=int(S * 0.035),
    outline=MAGENTA + (200,), width=8)
base.alpha_composite(glow(framel, 30, 1.4))
base.alpha_composite(framel)

img = base.convert("RGB")

# --- scanlines + grain ---------------------------------------------------
arr = np.asarray(img).astype(np.float32)
arr[::6, :, :] *= 0.86                                  # CRT scanlines
rng = np.random.default_rng(11)
arr += rng.normal(0, 9, (S, S, 1)).repeat(3, axis=2)     # grain
img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

out = sys.argv[1] if len(sys.argv) > 1 else "cover_neon.jpg"
img.save(out, quality=90)
print(f"wrote {out}")
