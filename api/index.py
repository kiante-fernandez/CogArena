import traceback
import sys

try:
    from harness.server import app
except Exception:
    # If the ASGI import fails, create a diagnostic ASGI app
    async def app(scope, receive, send):
        if scope["type"] == "http":
            body = traceback.format_exc().encode()
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
