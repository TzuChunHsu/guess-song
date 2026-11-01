"""Draw the share image (og.png) and app icons for the site.

    python3 make_assets.py <output-dir>
"""
import math, sys, pathlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Black.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
BG, CREAM, MUTED, RED, GOLD = (20, 16, 13), (244, 234, 216), (168, 151, 127), (255, 90, 60), (242, 193, 78)


def font(path, size, index=None):
    # the .ttc files hold JP, KR, SC, TC, HK faces; pick the Traditional Chinese one
    for i in ([index] if index is not None else range(10)):
        try:
            f = ImageFont.truetype(path, size, index=i)
            if "TC" in " ".join(f.getname()):
                return f
        except OSError:
            break
    return ImageFont.truetype(path, size)


def glow(img, xy, r, color, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], fill=color + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r * .45)))


def disc(img, cx, cy, r, label="耳"):
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(25, 21, 18))
    for k in range(int(r * .38), r, max(2, r // 60)):                 # grooves
        shade = 36 if (k // max(2, r // 60)) % 2 else 30
        d.ellipse([cx - k, cy - k, cx + k, cy + k], outline=(shade, shade - 6, shade - 10))
    sheen = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.pieslice([cx - r, cy - r, cx + r, cy + r], 200, 235, fill=(255, 255, 255, 22))
    sd.pieslice([cx - r, cy - r, cx + r, cy + r], 20, 55, fill=(255, 255, 255, 14))
    img.alpha_composite(sheen.filter(ImageFilter.GaussianBlur(max(1, r * .05))))
    lr = int(r * .36)
    d.ellipse([cx - lr, cy - lr, cx + lr, cy + lr], fill=RED)
    f = font(SERIF, int(lr * 1.05))
    d.text((cx, cy - lr * .04), label, font=f, fill=BG, anchor="mm")
    hr = max(2, r // 40)
    d.ellipse([cx + lr * .78 - hr, cy - hr, cx + lr * .78 + hr, cy + hr], fill=BG)


def og():
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), BG + (255,))
    glow(img, (1020, -40), 420, RED, 90)
    glow(img, (-80, 700), 380, GOLD, 50)
    disc(img, 930, 330, 270)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([80, 92, 392, 140], radius=24, outline=GOLD + (150,), width=2)
    d.text((236, 116), "華語金曲 · 猜歌王", font=font(SANS, 24), fill=GOLD, anchor="mm")
    t = font(SERIF, 150)
    d.text((72, 168), "耳熟", font=t, fill=CREAM)
    d.text((72, 330), "能詳", font=t, fill=RED)
    d.text((80, 530), "聽一小段旋律，猜出是哪首歌 · 好友連線對戰", font=font(SANS, 30), fill=MUTED)
    img.convert("RGB").save(OUT / "og.png", optimize=True)


def icon(size, name, pad=0.0):
    img = Image.new("RGBA", (size, size), BG + (255,))
    glow(img, (int(size * .8), int(size * .1)), int(size * .5), RED, 70)
    disc(img, size // 2, size // 2, int(size * (0.5 - pad)))
    img.convert("RGB").save(OUT / name, optimize=True)


OUT.mkdir(parents=True, exist_ok=True)
og()
icon(512, "icon-512.png", pad=.06)
icon(192, "icon-192.png", pad=.06)
icon(180, "apple-touch-icon.png", pad=.04)
print("assets written to", OUT)
