from fastapi import FastAPI

app = FastAPI()

@app.get("/api/test")
async def test():
    return {"status": "ok", "message": "minimal FastAPI works"}
