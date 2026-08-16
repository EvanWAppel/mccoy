"""Pre-send liveness check for the public demo.

Run this before linking a recruiter to the live site, so you never
point someone at a cold or crashed instance:

    uv run python scripts/check_live.py
    uv run python scripts/check_live.py https://mccoy.evanappel.me

Asserts the URL returns HTTP 200 and that a known server-rendered
marker (the og:title) is present in the HTML. Exits 0 on success,
non-zero otherwise. Deliberately hits the network and does not catch
errors silently — a failure should be loud.
"""

import logging
import sys
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEFAULT_URL = "https://mccoy.evanappel.me"
# Stable, server-rendered string (see _OG_TITLE in app.py). The demo
# grid itself is drawn by client-side callbacks, so assert on the
# initial HTML instead.
MARKER = "mccoy — Spotify dashboard by Evan Appel"


def check(url: str) -> bool:
    logger.info("Checking %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "mccoy-liveness"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.status
        body = resp.read().decode("utf-8", errors="replace")
    if status != 200:
        logger.error("FAIL: status %s (expected 200)", status)
        return False
    if MARKER not in body:
        logger.error("FAIL: marker %r not found in HTML", MARKER)
        return False
    logger.info("OK: 200 and marker present — demo is live.")
    return True


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    return 0 if check(url) else 1


if __name__ == "__main__":
    sys.exit(main())
