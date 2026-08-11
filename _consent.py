"""One-off consent capture for the PLAYLIST_* app.

Runs our OWN local HTTP server on the redirect port, captures the
authorization code from Spotify's redirect, exchanges it for a token,
and caches it to .cache-playlist. Avoids spotipy's fragile
browser/paste fallback. Prints the AUTH_URL, then blocks until the
redirect arrives.
"""

import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from auth import SCOPE

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("consent")
load_dotenv()

redirect = os.environ["PLAYLIST_REDIRECT_URI"]
port = urlparse(redirect).port or 8888

oauth = SpotifyOAuth(
    client_id=os.environ["PLAYLIST_CLIENT_ID"],
    client_secret=os.environ["PLAYLIST_CLIENT_SECRET"],
    redirect_uri=redirect,
    scope=SCOPE,
    open_browser=False,
    cache_path=".cache-playlist",
    # Force the consent screen every time. Without this, if the app was
    # authorized before with narrower scopes, Spotify silently re-issues
    # a token with the OLD scopes (no dialog), so newly-added scopes like
    # playlist-modify never get granted -> writes 403.
    show_dialog=True,
)

print("AUTH_URL:", oauth.get_authorize_url(), flush=True)


class Handler(BaseHTTPRequestHandler):
    captured = {}

    def do_GET(self):  # noqa: N802
        qs = parse_qs(urlparse(self.path).query)
        code = qs.get("code", [None])[0]
        err = qs.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if code:
            self.wfile.write(
                b"<h2>Authorized. You can close this tab.</h2>"
            )
            Handler.captured["code"] = code
        else:
            self.wfile.write(
                f"<h2>No code. error={err}</h2>".encode()
            )
            Handler.captured["error"] = err or "no code"

    def log_message(self, *args):  # silence default logging
        return


server = HTTPServer(("127.0.0.1", port), Handler)
log.info("LISTENING on 127.0.0.1:%d", port)
while "code" not in Handler.captured and "error" not in Handler.captured:
    server.handle_request()

if "code" in Handler.captured:
    oauth.get_access_token(Handler.captured["code"], as_dict=False)
    print("CONSENT_OK", flush=True)
else:
    print("CONSENT_FAILED:", Handler.captured.get("error"), flush=True)
