import asyncio
import hmac
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from harness.config import settings, get_turso_connect_args
from harness.db.models import (
    Base, SessionCreate, TrialDataSubmission, IncrementalDataSubmission,
    AdminReviewRequest,
)
from harness.session_manager import SessionManager
from scoring.score_session import score_task


_USE_LIBSQL = settings.DATABASE_URL.startswith("sqlite+libsql")

if _USE_LIBSQL:
    # sqlalchemy-libsql is sync-only; create sync engine + async wrapper
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker as sync_sessionmaker
    _sync_engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=get_turso_connect_args())
    _sync_session_factory = sync_sessionmaker(_sync_engine, expire_on_commit=False)
    engine = None  # not used directly
    async_session_factory = None  # not used directly
else:
    _sync_engine = None
    _sync_session_factory = None
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

PROJECT_ROOT = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

DOMAIN_LABELS = {
    "perception_attention": "Perception & Attention",
    "multi_armed_bandits": "Bandits & Exploration",
    "decision_making": "Decision-Making",
    "social_strategic": "Social & Strategic",
    "memory_learning": "Memory & Learning",
    "reinforcement_learning": "Reinforcement Learning",
}


_tasks_meta_cache: list[dict] | None = None


def _load_tasks_meta() -> list[dict]:
    """Load task metadata from all task_config.json files (cached after first call)."""
    global _tasks_meta_cache
    if _tasks_meta_cache is not None:
        return _tasks_meta_cache
    tasks = []
    for task_dir in sorted(settings.TASKS_DIR.iterdir()):
        config_path = task_dir / "task_config.json"
        if not (task_dir.is_dir() and config_path.exists()):
            continue
        with open(config_path) as f:
            config = json.load(f)

        params = config.get("parameters", {})

        # Count L3 signatures
        sig_path = task_dir / "scoring" / "level3_signatures.json"
        n_sigs = 0
        if sig_path.exists():
            with open(sig_path) as f:
                n_sigs = len(json.load(f).get("signatures", []))

        tasks.append({
            "task_id": config["task_id"],
            "task_name": config.get("task_name", config["task_id"]),
            "domain": config.get("domain", "unknown"),
            "domain_label": DOMAIN_LABELS.get(config.get("domain", ""), config.get("domain", "")),
            "description": config.get("description", ""),
            "citation": config.get("citation", ""),
            "n_trials": params.get("n_trials", 0),
            "n_signatures": n_sigs,
        })
    _tasks_meta_cache = tasks
    return tasks


class _SyncSessionAsyncWrapper:
    """Wraps a sync SQLAlchemy Session to match the AsyncSession interface.

    Used on Vercel where sqlalchemy-libsql only provides a sync driver.
    Delegates blocking calls to a thread pool via asyncio.to_thread.
    """

    def __init__(self, sync_session):
        self._s = sync_session

    async def execute(self, *a, **kw):
        return await asyncio.to_thread(self._s.execute, *a, **kw)

    async def commit(self):
        return await asyncio.to_thread(self._s.commit)

    async def delete(self, obj):
        return await asyncio.to_thread(self._s.delete, obj)

    def add(self, obj):
        self._s.add(obj)


_db_initialized = False
_db_lock = asyncio.Lock()


async def _ensure_db():
    """Lazily initialize database tables (needed for serverless where lifespan may not run)."""
    global _db_initialized
    if _db_initialized:
        return
    async with _db_lock:
        if not _db_initialized:
            if _USE_LIBSQL:
                Base.metadata.create_all(_sync_engine)
            else:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            _db_initialized = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: ensure tables exist, then yield a DB session."""
    await _ensure_db()
    if _USE_LIBSQL:
        session = _sync_session_factory()
        try:
            yield _SyncSessionAsyncWrapper(session)
        finally:
            session.close()
    else:
        async with async_session_factory() as session:
            yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("VERCEL"):
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        await _ensure_db()
    yield
    if not os.environ.get("VERCEL") and engine is not None:
        await engine.dispose()


app = FastAPI(title="CogArena", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Website Routes ---

@app.get("/", include_in_schema=False)
async def landing_page(request: Request):
    tasks = _load_tasks_meta()
    domains = set(t["domain"] for t in tasks)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "task_count": len(tasks),
        "domain_count": len(domains),
    })


@app.get("/catalog", include_in_schema=False)
async def catalog_page(request: Request):
    tasks = _load_tasks_meta()
    domains = set(t["domain"] for t in tasks)
    return templates.TemplateResponse("catalog.html", {
        "request": request,
        "tasks": tasks,
        "domains": domains,
    })


@app.get("/catalog/{task_id}", include_in_schema=False)
async def task_detail_page(request: Request, task_id: str):
    tasks = _load_tasks_meta()
    task = next((t for t in tasks if t["task_id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "task": task,
    })


@app.get("/leaderboard", include_in_schema=False)
async def leaderboard_page(request: Request):
    return templates.TemplateResponse("leaderboard.html", {"request": request})


@app.get("/try", include_in_schema=False)
async def try_page(request: Request):
    tasks = _load_tasks_meta()
    return templates.TemplateResponse("try.html", {
        "request": request,
        "tasks": tasks,
    })


@app.get("/submit", include_in_schema=False)
async def submit_page(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return templates.TemplateResponse("submit.html", {
        "request": request,
        "base_url": base_url,
    })


@app.get("/skill.md", include_in_schema=False)
async def skill_file():
    skill_path = PROJECT_ROOT / "static" / "skill.md"
    return PlainTextResponse(skill_path.read_text(), media_type="text/markdown")


# --- API Routes ---

@app.get("/api/info", summary="Server info and available endpoints")
async def api_info():
    task_ids = []
    for task_dir in sorted(settings.TASKS_DIR.iterdir()):
        if task_dir.is_dir() and (task_dir / "task_config.json").exists():
            task_ids.append(task_dir.name)

    return {
        "name": "CogArena",
        "version": "0.1.0",
        "description": "Benchmark for testing AI agents on interactive behavioral experiments",
        "docs": "/docs",
        "endpoints": {
            "info": "GET /api/info",
            "health": "GET /api/health",
            "tasks": "GET /api/tasks",
            "create_session": "POST /api/sessions",
            "session_status": "GET /api/sessions/{session_id}",
            "submit_data": "POST /api/data/{session_id}/{task_id}",
            "save_partial": "PATCH /api/data/{session_id}/{task_id}",
            "evaluate": "POST /api/evaluate/{session_id}",
            "results": "GET /api/results/{session_id}",
            "leaderboard": "GET /api/leaderboard",
        },
        "tasks": task_ids,
    }


@app.get("/api/health", summary="Health check")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/tasks", summary="List all available tasks with configuration")
async def list_tasks():
    return {"tasks": _load_tasks_meta()}


@app.post("/api/sessions", summary="Create a new evaluation session")
async def create_session(data: SessionCreate, db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    return await mgr.create_session(data)


@app.get("/api/sessions/{session_id}", summary="Get session status and task completion")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    try:
        return await mgr.get_session_status(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/data/{session_id}/{task_id}", summary="Submit trial data for a task")
async def submit_data(session_id: str, task_id: str, body: TrialDataSubmission, db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    try:
        await mgr.submit_trial_data(
            session_id, task_id, body.trial_data, body.metadata,
            is_complete=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "session_id": session_id, "task_id": task_id}


@app.patch("/api/data/{session_id}/{task_id}", summary="Incrementally save partial trial data")
async def save_partial_data(session_id: str, task_id: str, body: IncrementalDataSubmission, db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    try:
        await mgr.submit_trial_data(
            session_id, task_id, body.trial_data, body.metadata,
            is_complete=body.is_complete,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "saved", "session_id": session_id, "task_id": task_id,
            "n_trials": len(body.trial_data), "is_complete": body.is_complete}


@app.post("/api/evaluate/{session_id}/{task_id}", summary="Score a single task in a session")
async def evaluate_task(session_id: str, task_id: str, db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    task_results = await mgr.get_all_task_results(session_id)
    tr = next((t for t in task_results if t.task_id == task_id), None)
    if not tr:
        raise HTTPException(status_code=404, detail=f"No data for task {task_id}")

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
    return {"status": "scored", "session_id": session_id, "task_id": task_id}


@app.post("/api/evaluate/{session_id}", summary="Trigger scoring for all tasks in a session")
async def evaluate_session(session_id: str, db: AsyncSession = Depends(get_db)):
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


@app.get("/api/results/{session_id}", summary="Get scorecard for a scored session")
async def get_results(session_id: str, db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    try:
        return await mgr.get_scorecard(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/leaderboard", summary="Get ranked leaderboard of all scored sessions")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    mgr = SessionManager(db, settings.TASKS_DIR)
    entries = await mgr.get_leaderboard()
    total_tasks = len(mgr.get_available_tasks("_"))
    return {"total_tasks": total_tasks, "entries": entries}


# --- Admin Routes ---

async def verify_admin(x_admin_key: str = Header(...)):
    if not settings.ADMIN_API_KEY or not hmac.compare_digest(x_admin_key, settings.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid admin key")


@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/api/admin/submissions", summary="List scored sessions for admin review")
async def admin_list_submissions(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin),
):
    mgr = SessionManager(db, settings.TASKS_DIR)
    return {"submissions": await mgr.get_submissions(status)}


@app.post("/api/admin/submissions/{session_id}/approve", summary="Approve a submission")
async def admin_approve(
    session_id: str,
    body: AdminReviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin),
):
    mgr = SessionManager(db, settings.TASKS_DIR)
    try:
        reviewed_by = body.reviewed_by if body else None
        notes = body.notes if body else None
        return await mgr.approve_session(session_id, reviewed_by, notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/submissions/{session_id}/reject", summary="Reject a submission")
async def admin_reject(
    session_id: str,
    body: AdminReviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin),
):
    mgr = SessionManager(db, settings.TASKS_DIR)
    try:
        reviewed_by = body.reviewed_by if body else None
        notes = body.notes if body else None
        return await mgr.reject_session(session_id, reviewed_by, notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Static Files (mounted last so explicit routes take priority) ---

static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

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
