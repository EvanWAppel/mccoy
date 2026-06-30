"""Generate the PWA app icons (run once; outputs committed to assets/).

    uv run python scripts/make_icons.py

A simple vinyl-record motif: Spotify-green disc on the app's dark
background, with a groove ring, a dark label, and a spindle hole.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (18, 18, 18)  # #121212
SURFACE = (30, 30, 30)  # #1E1E1E
GREEN = (29, 185, 84)  # #1DB954
WHITE = (255, 255, 255)
GREY = (179, 179, 179)  # #B3B3B3
ASSETS = Path(__file__).resolve().parent.parent / "assets"

# macOS system fonts, with graceful fallback to PIL's bitmap default.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _circle(draw, cx, cy, r, fill=None, outline=None, width=1):
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=fill,
        outline=outline,
        width=width,
    )


def make_icon(size: int, disc_ratio: float, path: Path) -> None:
    # 4x supersample for smooth edges, then downscale.
    s = size * 4
    img = Image.new("RGBA", (s, s), BG + (255,))
    d = ImageDraw.Draw(img)
    c = s / 2
    disc = s * disc_ratio
    _circle(d, c, c, disc, fill=GREEN)
    _circle(d, c, c, disc * 0.70, outline=BG, width=int(s * 0.012))
    _circle(d, c, c, disc * 0.34, fill=BG)
    _circle(d, c, c, disc * 0.06, fill=GREEN)
    img = img.resize((size, size), Image.LANCZOS)
    img.save(path)
    print("wrote", path.name)


def make_og_image(path: Path) -> None:
    # MM-02: 1200x630 social/link-preview card. Vinyl disc on the left,
    # title + tagline on the right, on the app's dark background.
    w, h = 1200, 630
    scale = 2  # supersample for crisp text + edges
    img = Image.new("RGBA", (w * scale, h * scale), BG + (255,))
    d = ImageDraw.Draw(img)

    # disc, vertically centered on the left third
    cx, cy = int(w * 0.27 * scale), int(h * 0.5 * scale)
    disc = int(h * 0.34 * scale)
    _circle(d, cx, cy, disc, fill=GREEN)
    _circle(d, cx, cy, int(disc * 0.70), outline=BG, width=int(8 * scale))
    _circle(d, cx, cy, int(disc * 0.34), fill=BG)
    _circle(d, cx, cy, int(disc * 0.06), fill=GREEN)

    # text block on the right
    tx = int(w * 0.46 * scale)
    title_font = _font(120 * scale)
    tag_font = _font(34 * scale)
    sub_font = _font(28 * scale)

    d.text((tx, int(h * 0.30 * scale)), "mccoy", font=title_font, fill=WHITE)
    d.text(
        (tx, int(h * 0.52 * scale)),
        "Spotify listening, visualized —",
        font=tag_font, fill=GREEN,
    )
    d.text(
        (tx, int(h * 0.585 * scale)),
        "and a crate of records to dig through.",
        font=tag_font, fill=GREY,
    )
    d.text(
        (tx, int(h * 0.72 * scale)),
        "by Evan Appel",
        font=sub_font, fill=GREY,
    )

    img = img.resize((w, h), Image.LANCZOS).convert("RGB")
    img.save(path)
    print("wrote", path.name)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    # "any" icons: disc fills most of the square
    make_icon(192, 0.42, ASSETS / "icon-192.png")
    make_icon(512, 0.42, ASSETS / "icon-512.png")
    # maskable: keep the disc inside the ~80% safe zone
    make_icon(512, 0.32, ASSETS / "icon-maskable-512.png")
    # apple-touch-icon (180px is the iOS standard)
    make_icon(180, 0.42, ASSETS / "apple-touch-icon.png")
    # MM-02: 1200x630 Open Graph / Twitter link-preview card
    make_og_image(ASSETS / "og-image.png")


if __name__ == "__main__":
    main()
