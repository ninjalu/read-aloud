"""Generate the Read Aloud app icon (a page with sound waves) as a 1024px PNG.

Run:  .venv/bin/python make_icon.py
Then build the .icns with make_icon.sh.
"""
from PIL import Image, ImageDraw

S = 1024          # final size
SS = 2            # supersample factor for smooth edges
W = S * SS

TOP = (84, 124, 255)    # indigo
BOT = (126, 58, 240)    # violet
PAGE = (255, 255, 255, 255)
LINE = (150, 162, 205, 255)

img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

# --- gradient background, clipped to a rounded square (macOS "squircle" look) ---
grad = Image.new("RGB", (1, W))
for y in range(W):
    t = y / (W - 1)
    grad.putpixel((0, y), tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3)))
grad = grad.resize((W, W))

margin = int(W * 0.085)
radius = int(W * 0.225)
mask = Image.new("L", (W, W), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [margin, margin, W - margin, W - margin], radius=radius, fill=255)
img.paste(grad, (0, 0), mask)

draw = ImageDraw.Draw(img)

# --- the page (a document) ---
pw, ph = int(W * 0.34), int(W * 0.46)
px, py = int(W * 0.28), (W - ph) // 2
# soft shadow
shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle(
    [px + int(W*0.012), py + int(W*0.016), px + pw + int(W*0.012), py + ph + int(W*0.016)],
    radius=int(W * 0.03), fill=(20, 20, 60, 90))
img.alpha_composite(shadow)
draw.rounded_rectangle([px, py, px + pw, py + ph], radius=int(W * 0.03), fill=PAGE)

# text lines on the page
lx0 = px + int(pw * 0.16)
lh = int(ph * 0.05)
for i in range(4):
    ly = py + int(ph * 0.20) + i * int(ph * 0.17)
    lx1 = px + int(pw * (0.84 if i < 3 else 0.58))   # last line shorter
    draw.rounded_rectangle([lx0, ly, lx1, ly + lh], radius=lh // 2, fill=LINE)

# --- sound waves emanating to the right (the page being "read aloud") ---
cx, cy = int(W * 0.60), W // 2
wave_w = int(W * 0.026)
for r in (0.11, 0.17, 0.23):
    rr = int(W * r)
    draw.arc([cx - rr, cy - rr, cx + rr, cy + rr],
             start=-48, end=48, fill=(255, 255, 255, 255), width=wave_w)
# small origin dot
dot = int(W * 0.018)
draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=(255, 255, 255, 255))

img = img.resize((S, S), Image.LANCZOS)
img.save("icon_master.png")
print("wrote icon_master.png")
