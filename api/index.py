import sys
import traceback

try:
    from harness.server import app
except Exception as e:
    # Create a minimal ASGI app that reports the import error
    from fastapi import FastAPI
    app = FastAPI()

    error_msg = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"

    @app.get("/{path:path}")
    async def debug_error(path: str = ""):
        return {
            "error": "Failed to import harness.server",
            "detail": error_msg,
            "python_version": sys.version,
            "sys_path": sys.path,
        }
