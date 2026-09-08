#!/usr/bin/env python3
"""Generate the Open Graph social card (1200x630) for the landing page."""
from PIL import Image, ImageDraw, ImageFilter
import math

W, H = 1200, 630

# Deep glass background
img = Image.new("RGB", (W, H), (6, 10, 18))
d = ImageDraw.Draw(img)

# Glow orbs (lilac / cyan)
def orb(cx, cy, radius, color):
    layer = Image.new("L", (W, H), 0)
    dl = ImageDraw.Draw(layer)
    for i in range(radius, 0, -8):
        a = int(140 * (1 - i / radius))
        dl.ellipse([cx - i, cy - i, cx + i, cy + i], fill=a)
    layer = layer.filter(ImageFilter.GaussianBlur(60))
    color_layer = Image.new("RGB", (W, H), color)
    img.paste(Image.composite(color_layer, Image.new("RGB", (W, H), (0, 0, 0)), layer), (0, 0), layer)

orb(200, 150, 380, (107, 82, 255))    # violet
orb(1000, 480, 420, (56, 189, 248))   # cyan
orb(950, 120, 300, (53, 121, 255))    # blue

d = ImageDraw.Draw(img)

# Panda face (minimalist white circle + ears + eyes)
cx, cy, r = 190, 315, 105
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(240, 246, 252))
# ears
d.ellipse([cx - r - 28, cy - r - 22, cx - r + 28, cy - r + 52], fill=(240, 246, 252))
d.ellipse([cx + r - 28, cy - r - 22, cx + r + 28, cy - r + 52], fill=(240, 246, 252))
# ear inner dark
d.ellipse([cx - r - 14, cy - r - 8, cx - r + 14, cy - r + 36], fill=(30, 36, 50))
d.ellipse([cx + r - 14, cy - r - 8, cx + r + 14, cy - r + 36], fill=(30, 36, 50))
# eyes
d.ellipse([cx - 42, cy - 20, cx - 12, cy + 18], fill=(20, 24, 36))
d.ellipse([cx + 12, cy - 20, cx + 42, cy + 18], fill=(20, 24, 36))
# eye shine
d.ellipse([cx - 36, cy - 14, cx - 28, cy - 4], fill=(255, 255, 255))
d.ellipse([cx + 18, cy - 14, cx + 26, cy - 4], fill=(255, 255, 255))
# nose
d.ellipse([cx - 10, cy + 18, cx + 10, cy + 36], fill=(20, 24, 36))
# mouth
d.arc([cx - 20, cy + 18, cx + 20, cy + 46], 20, 160, fill=(20, 24, 36), width=4)

# Text
from PIL import ImageFont
def load_font(size, bold=False):
    for path in [
        r"C:/Windows/Fonts/arialbd.ttf" if bold else r"C:/Windows/Fonts/arial.ttf",
        r"C:/Windows/Fonts/segoeuib.ttf" if bold else r"C:/Windows/Fonts/segoeui.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

# Title
t1 = "Lightpanda Session Bridge"
t2 = "Transfer real logins to headless AI agents"
t3 = "github.com/Raknaos/lightpanda-session-bridge"

def text_w(canvas, s, f):
    b = canvas.textbbox((0, 0), s, font=f)
    return b[2] - b[0]

f1 = load_font(64, bold=True)
f2 = load_font(34)
f3 = load_font(26, bold=True)

# wrap title if too wide
title_text = t1
w1 = text_w(d, title_text, f1)
if w1 > 780:
    f1 = load_font(48, bold=True)
    w1 = text_w(d, title_text, f1)

x0 = 330
d.text((x0, 150), title_text, fill=(240, 246, 252), font=f1)
d.text((x0, 260), t2, fill=(210, 226, 255), font=f2)
d.text((x0, 420), t3, fill=(150, 175, 220), font=f3)

# Badge pill "Open Source · MIT"
bx0, by0, bw, bh = x0, 340, 300, 46
d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=23, fill=(53, 121, 255, 90), outline=(120, 150, 255))
d.text((bx0 + 18, by0 + 9), "Zero credentials · Zero secrets", fill=(210, 225, 255), font=load_font(20))

img.save("og-image.png", "PNG")
print("og-image.png générée:", img.size)
