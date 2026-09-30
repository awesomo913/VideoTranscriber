"""Generate docs/assets/icon-256.png and docs/assets/social-preview.png.

VideoTranscriber has no existing app icon, so this draws a simple
rounded-square teal->blue gradient tile with a white "play" glyph (matching
banner.svg's app tile) at 256x256, plus a 1280x640 social preview card for
link unfurls. One-off content-generation tool, not part of the app itself —
its dependency (Pillow) is intentionally not in requirements.txt:

    pip install pillow
    python scripts/make_icon_and_social.py

Output: docs/assets/icon-256.png, docs/assets/social-preview.png
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "docs", "assets")

TEAL = (46, 196, 182)
BLUE = (77, 150, 255)
BG = (20, 20, 31)
FG = (245, 247, 250)
MUTED = (169, 180, 196)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient_rounded_square(size: int, radius: int) -> Image.Image:
    scale = 4
    big = size * scale
    grad = Image.new("RGB", (big, big))
    px = grad.load()
    for y in range(big):
        for x in range(big):
            t = (x + y) / (2 * big)
            px[x, y] = _lerp(TEAL, BLUE, t)

    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, big - 1, big - 1], radius=radius * scale, fill=255
    )
    tile = Image.new("RGBA", (big, big))
    tile.paste(grad, (0, 0), mask)
    return tile.resize((size, size), Image.LANCZOS)


def _play_glyph(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float) -> None:
    w = 40 * scale
    h = 52 * scale
    pts = [
        (cx - w * 0.35, cy - h * 0.5),
        (cx - w * 0.35, cy + h * 0.5),
        (cx + w * 0.55, cy),
    ]
    draw.polygon(pts, fill=FG)
    bar_w = 48 * scale
    draw.rounded_rectangle(
        [cx - bar_w / 2, cy + h * 0.62, cx + bar_w / 2, cy + h * 0.62 + 6 * scale],
        radius=3 * scale, fill=(255, 255, 255, 230),
    )


def make_icon() -> Image.Image:
    size = 256
    icon = _gradient_rounded_square(size, radius=size // 4)
    draw = ImageDraw.Draw(icon)
    _play_glyph(draw, size / 2, size / 2 - 4, scale=size / 104)
    return icon


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _font_regular(size: int) -> ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_social_preview(icon: Image.Image) -> Image.Image:
    w, h = 1280, 640
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    # Faint glow
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([w - 700, h // 2 - 260, w - 40, h // 2 + 260], fill=(77, 150, 255, 40))
    glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(80))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"))

    icon_big = icon.resize((220, 220), Image.LANCZOS)
    img.paste(icon_big, (110, 210), icon_big)

    title_font = _font(64)
    sub_font = _font_regular(28)
    draw.text((110, 450), "VideoTranscriber", font=title_font, fill=FG)
    draw.text(
        (112, 525), "Turn video and audio into text — 100% offline.",
        font=sub_font, fill=MUTED,
    )

    return img


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    icon = make_icon()
    icon_path = os.path.join(ASSETS, "icon-256.png")
    icon.save(icon_path)
    print(f"[make_icon] wrote {os.path.abspath(icon_path)}")

    social = make_social_preview(icon)
    social_path = os.path.join(ASSETS, "social-preview.png")
    social.save(social_path)
    print(f"[make_icon] wrote {os.path.abspath(social_path)}")


if __name__ == "__main__":
    main()
