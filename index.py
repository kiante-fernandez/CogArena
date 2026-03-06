from contextlib import asynccontextmanager
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    yield
    print("Shutting down...")


app = FastAPI(lifespan=lifespan)


@app.get("/api/test")
async def test():
    return {"status": "ok", "message": "FastAPI with lifespan works"}
