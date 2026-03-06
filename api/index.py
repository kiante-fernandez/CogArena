from http.server import BaseHTTPRequestHandler
import json
import sys


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        errors = []
        imports_to_test = [
            "pydantic",
            "pydantic_core",
            "fastapi",
            "sqlalchemy",
            "aiosqlite",
            "jinja2",
            "scipy",
            "numpy",
        ]

        for mod in imports_to_test:
            try:
                __import__(mod)
                errors.append({"module": mod, "status": "ok"})
            except Exception as e:
                errors.append({
                    "module": mod,
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                })

        body = json.dumps({
            "python_version": sys.version,
            "platform": sys.platform,
            "imports": errors,
        }, indent=2)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())
