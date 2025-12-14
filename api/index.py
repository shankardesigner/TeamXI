"""Vercel entrypoint.

Vercel routes only the exact path /api/index to this file, and a rewrite
replaces the request path rather than preserving it. So vercel.json forwards the
real path as ?__path=, and this shim puts it back on the ASGI scope before
handing off to the FastAPI app.
"""
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import app as api_app  # noqa: E402

PATH_PARAM = "__path"


class RestoreOriginalPath:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            params = parse_qsl(scope.get("query_string", b"").decode(), keep_blank_values=True)
            forwarded = [v for k, v in params if k == PATH_PARAM]
            if forwarded:
                scope = dict(scope)
                scope["path"] = "/" + forwarded[0].lstrip("/")
                scope["raw_path"] = scope["path"].encode()
                rest = [(k, v) for k, v in params if k != PATH_PARAM]
                scope["query_string"] = urlencode(rest).encode()
        await self.inner(scope, receive, send)


app = RestoreOriginalPath(api_app)
