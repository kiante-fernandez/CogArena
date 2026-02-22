import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from harness.config import settings
from harness.db.models import (
    Base, SessionCreate, TrialDataSubmission,
)
from harness.session_manager import SessionManager
from scoring.score_session import score_task

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="CogArena", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_manager() -> SessionManager:
    async with async_session_factory() as db:
        yield SessionManager(db, settings.TASKS_DIR)


# --- API Routes ---

@app.get("/")
async def root():
    task_ids = []
    for task_dir in sorted(settings.TASKS_DIR.iterdir()):
        if task_dir.is_dir() and (task_dir / "task_config.json").exists():
            task_ids.append(task_dir.name)

    return {
        "name": "CogArena",
        "version": "0.1.0",
        "description": "Benchmark for testing AI agents on interactive cognitive psychology experiments",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /api/health",
            "create_session": "POST /api/sessions",
            "session_status": "GET /api/sessions/{session_id}",
            "submit_data": "POST /api/data/{session_id}/{task_id}",
            "evaluate": "POST /api/evaluate/{session_id}",
            "results": "GET /api/results/{session_id}",
            "leaderboard": "GET /api/leaderboard",
        },
        "tasks": task_ids,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/sessions")
async def create_session(data: SessionCreate):
    async with async_session_factory() as db:
        mgr = SessionManager(db, settings.TASKS_DIR)
        return await mgr.create_session(data)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    async with async_session_factory() as db:
        mgr = SessionManager(db, settings.TASKS_DIR)
        try:
            return await mgr.get_session_status(session_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/data/{session_id}/{task_id}")
async def submit_data(session_id: str, task_id: str, body: TrialDataSubmission):
    async with async_session_factory() as db:
        mgr = SessionManager(db, settings.TASKS_DIR)
        try:
            await mgr.submit_trial_data(
                session_id, task_id, body.trial_data, body.metadata
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "session_id": session_id, "task_id": task_id}


@app.post("/api/evaluate/{session_id}")
async def evaluate_session(session_id: str):
    async with async_session_factory() as db:
        mgr = SessionManager(db, settings.TASKS_DIR)
        task_results = await mgr.get_all_task_results(session_id)

        if not task_results:
            raise HTTPException(status_code=404, detail="No task data found for session")

        for tr in task_results:
            trial_data = json.loads(tr.trial_data)
            result = score_task(trial_data, tr.task_id, settings.TASKS_DIR)

            composite_info = result["composite"]
            await mgr.save_score(
                session_id=session_id,
                task_id=tr.task_id,
                l1=result["l1"]["score"],
                l2=result["l2"]["score"],
                l3=result["l3"]["score"],
                composite=composite_info["composite_score"],
                details=result,
            )

        await mgr.mark_session_scored(session_id)

    return {"status": "scored", "session_id": session_id}


@app.get("/api/results/{session_id}")
async def get_results(session_id: str):
    async with async_session_factory() as db:
        mgr = SessionManager(db, settings.TASKS_DIR)
        try:
            return await mgr.get_scorecard(session_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/leaderboard")
async def get_leaderboard():
    async with async_session_factory() as db:
        mgr = SessionManager(db, settings.TASKS_DIR)
        entries = await mgr.get_leaderboard()
        return {"entries": entries}


# --- Static Files (mounted last) ---

if settings.JSPSYCH_DIR.exists():
    app.mount(
        "/jsPsych-8.2.3",
        StaticFiles(directory=str(settings.JSPSYCH_DIR)),
        name="jspsych",
    )

if settings.TASKS_DIR.exists():
    app.mount(
        "/tasks",
        StaticFiles(directory=str(settings.TASKS_DIR), html=True),
        name="tasks",
    )
