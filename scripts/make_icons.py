"""Generate the PWA app icons (run once; outputs committed to assets/).

    uv run python scripts/make_icons.py

A simple vinyl-record motif: Spotify-green disc on the app's dark
background, with a groove ring, a dark label, and a spindle hole.
"""
from pathlib import Path

from PIL import Image, ImageDraw

BG = (18, 18, 18)  # #121212
GREEN = (29, 185, 84)  # #1DB954
ASSETS = Path(__file__).resolve().parent.parent / "assets"


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


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    # "any" icons: disc fills most of the square
    make_icon(192, 0.42, ASSETS / "icon-192.png")
    make_icon(512, 0.42, ASSETS / "icon-512.png")
    # maskable: keep the disc inside the ~80% safe zone
    make_icon(512, 0.32, ASSETS / "icon-maskable-512.png")
    # apple-touch-icon (180px is the iOS standard)
    make_icon(180, 0.42, ASSETS / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
