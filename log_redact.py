"""Redact secrets from text bound for the logs (XX-09).

libpq and other clients quote connection strings in their error
messages, so a logged traceback can carry a database password. These
helpers replace only the secret parts of the text. The exception
itself is never changed, wrapped or hidden.
"""

import re
import traceback

MASK = "***"

# `scheme://user:pass@host`, also the malformed `scheme:/user:pass@`
# and a password with no user (`redis://:pass@host`). The user part
# cannot contain "/", so the scheme's own ":" never starts a match.
# The password runs to the last "@" before whitespace, "/" or a quote,
# so an unencoded "@" in it is still covered.
_URL_PASSWORD = re.compile(r"""([\w.%+~-]*):([^\s/'"]+)@""")

# libpq key/value form: `password=secret` or `password = 'se cret'`.
_KV_PASSWORD = re.compile(
    r"""(\b(?:password|passwd|pwd)\s*=\s*)('(?:[^'\\]|\\.)*'|[^\s'"]+)""",
    re.IGNORECASE,
)

# Anthropic API keys.
_API_KEY = re.compile(r"(sk-ant-)[\w-]+")


def redact(text: str) -> str:
    """Return `text` with passwords and API keys replaced by MASK."""
    text = _URL_PASSWORD.sub(rf"\1:{MASK}@", text)
    text = _KV_PASSWORD.sub(rf"\1{MASK}", text)
    return _API_KEY.sub(rf"\1{MASK}", text)


def format_exception(exc: BaseException) -> str:
    """The full traceback of `exc`, chained exceptions included,
    with secrets redacted. Type, frames and message are kept."""
    return redact("".join(traceback.format_exception(exc)))
