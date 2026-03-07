"""Vercel serverless entry point — wraps the FastAPI app with Mangum."""

from mangum import Mangum

from harness.server import app

handler = Mangum(app, lifespan="off")
