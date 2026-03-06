from http.server import BaseHTTPRequestHandler
import json
import sys
import traceback


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = {}
        try:
            from harness.server import app
            result["status"] = "ok"
            result["app_title"] = app.title
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"{type(e).__name__}: {e}"
            result["traceback"] = traceback.format_exc()

        result["python_version"] = sys.version

        body = json.dumps(result, indent=2)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())
