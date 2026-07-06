"""Podcast cover v3 - designed to blush.design's cover-art rules:
one simple idea (text lines becoming sound), an analogous neon scheme
(cyan -> violet), and legibility at 100x100.

Run:  .venv/bin/python make_cover_v3.py [out.jpg]
"""
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 3000
BG = (7, 11, 24)            # deep blue-black
CYAN = (23, 233, 255)
VIOLET = (106, 92, 255)
INK = (245, 247, 255)

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


def glow(layer, radius, strength=1.0):
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        a = g.getchannel("A").point(lambda v: min(255, int(v * strength)))
        g.putalpha(a)
    return g


base = Image.new("RGBA", (S, S), BG + (255,))

# subtle centre bloom so the dark ground isn't flat
yy, xx = np.mgrid[0:S, 0:S]
d = np.sqrt((xx - S / 2) ** 2 + (yy - S * 0.42) ** 2) / (S * 0.75)
bloom = np.clip(1 - d, 0, 1) ** 2.4
amb = np.stack([bloom * VIOLET[c] * 0.22 for c in range(3)], axis=2)
base = Image.fromarray(
    np.clip(np.asarray(base.convert("RGB")) + amb, 0, 255).astype(np.uint8)
).convert("RGBA")

# --- the mark: two text lines, the third erupts into a waveform --------
mark = Image.new("RGBA", (S, S), (0, 0, 0, 0))
md = ImageDraw.Draw(mark)

left, right = int(S * 0.19), int(S * 0.81)
bar_h = int(S * 0.032)
ys = [int(S * 0.26), int(S * 0.38), int(S * 0.50)]

# line 1: full width | line 2: shorter (a paragraph, not a logo stripe)
md.rounded_rectangle([left, ys[0], right, ys[0] + bar_h],
                     radius=bar_h // 2, fill=lerp(CYAN, VIOLET, 0.0) + (255,))
md.rounded_rectangle([left, ys[1], int(S * 0.62), ys[1] + bar_h],
                     radius=bar_h // 2, fill=lerp(CYAN, VIOLET, 0.35) + (255,))

# line 3: the text becomes sound - waveform spikes on the same baseline
random.seed(5)
cy = ys[2] + bar_h // 2
spike_w, gap = 44, 38
x, i = left, 0
while x + spike_w <= right:
    t = (x - left) / (right - left)
    cluster = abs(np.sin(i * 0.52)) * abs(np.sin(i * 0.13 + 0.9))
    h = int(bar_h * 0.7 + S * 0.075 * cluster * random.uniform(0.5, 1.0))
    md.rounded_rectangle([x, cy - h, x + spike_w, cy + h],
                         radius=spike_w // 2,
                         fill=lerp(CYAN, VIOLET, 0.35 + 0.65 * t) + (255,))
    x += spike_w + gap
    i += 1

base.alpha_composite(glow(mark, 60, 1.5))
base.alpha_composite(glow(mark, 16, 1.2))
base.alpha_composite(mark)

# --- wordmark: one clean line, white, quiet glow ------------------------
word = Image.new("RGBA", (S, S), (0, 0, 0, 0))
wd = ImageDraw.Draw(word)
font = load_face(int(S * 0.155))
wd.text((S // 2, int(S * 0.76)), "READ ALOUD", font=font,
        anchor="mm", fill=INK + (255,))
base.alpha_composite(glow(word, 40, 0.5))
base.alpha_composite(word)

img = base.convert("RGB")

# film grain, faint
rng = np.random.default_rng(5)
arr = np.asarray(img).astype(np.float32)
arr += rng.normal(0, 7, (S, S, 1)).repeat(3, axis=2)
img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

out = sys.argv[1] if len(sys.argv) > 1 else "cover_v3.jpg"
img.save(out, quality=90)
print(f"wrote {out}")
