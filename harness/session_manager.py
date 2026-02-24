import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from harness.config import settings
from harness.db.models import (
    Session, TaskResult, Score,
    SessionCreate, SessionResponse, TaskInfo, TaskScore, ScorecardResponse,
)
from scoring.score_session import score_task

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, db: AsyncSession, tasks_dir: Path):
        self.db = db
        self.tasks_dir = tasks_dir

    async def create_session(self, data: SessionCreate) -> SessionResponse:
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            agent_name=data.agent_name,
            scaffold=data.scaffold,
            model_name=data.model_name,
            observation_mode=data.observation_mode,
            status="created",
        )
        self.db.add(session)
        await self.db.commit()

        tasks = await self._get_tasks_with_status(session_id)
        return SessionResponse(session_id=session_id, tasks=tasks, status="created")

    def get_available_tasks(self, session_id: str) -> list[TaskInfo]:
        tasks = []
        for task_dir in sorted(self.tasks_dir.iterdir()):
            config_path = task_dir / "task_config.json"
            if task_dir.is_dir() and config_path.exists():
                tasks.append(TaskInfo(
                    task_id=task_dir.name,
                    url=f"/tasks/{task_dir.name}/?session_id={session_id}",
                ))
        return tasks

    async def _get_tasks_with_status(self, session_id: str) -> list[TaskInfo]:
        completed_result = await self.db.execute(
            select(TaskResult.task_id).where(TaskResult.session_id == session_id)
        )
        completed_ids = set(completed_result.scalars().all())

        tasks = []
        for task_dir in sorted(self.tasks_dir.iterdir()):
            config_path = task_dir / "task_config.json"
            if task_dir.is_dir() and config_path.exists():
                tasks.append(TaskInfo(
                    task_id=task_dir.name,
                    url=f"/tasks/{task_dir.name}/?session_id={session_id}",
                    completed=task_dir.name in completed_ids,
                ))
        return tasks

    async def validate_session_active(self, session_id: str) -> Session:
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        if session.status == "scored":
            raise ValueError(f"Session {session_id} already scored")
        if session.created_at:
            age = datetime.now(timezone.utc) - session.created_at.replace(tzinfo=timezone.utc)
            if age.total_seconds() > settings.SESSION_TIMEOUT_HOURS * 3600:
                raise ValueError(f"Session {session_id} expired")
        return session

    async def submit_trial_data(
        self, session_id: str, task_id: str, trial_data: list[dict], metadata: dict | None = None
    ) -> None:
        await self.validate_session_active(session_id)

        existing = await self.db.execute(
            select(TaskResult).where(
                TaskResult.session_id == session_id,
                TaskResult.task_id == task_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"Data already submitted for {task_id} in session {session_id}")

        task_result = TaskResult(
            session_id=session_id,
            task_id=task_id,
            trial_data=json.dumps(trial_data),
        )
        self.db.add(task_result)

        result = await self.db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.status = "in_progress"
        await self.db.commit()

        await self._auto_evaluate_if_complete(session_id)

    async def _auto_evaluate_if_complete(self, session_id: str) -> None:
        """Auto-trigger scoring when all tasks have been submitted."""
        total_tasks = sum(
            1 for d in self.tasks_dir.iterdir()
            if d.is_dir() and (d / "task_config.json").exists()
        )
        submitted = await self.db.execute(
            select(TaskResult.task_id).where(TaskResult.session_id == session_id)
        )
        submitted_ids = set(submitted.scalars().all())
        if len(submitted_ids) < total_tasks:
            return

        logger.info("All %d tasks submitted for session %s — auto-evaluating", total_tasks, session_id)
        task_results = await self.get_all_task_results(session_id)
        for tr in task_results:
            trial_data = json.loads(tr.trial_data)
            result = score_task(trial_data, tr.task_id, self.tasks_dir)
            composite_info = result["composite"]
            await self.save_score(
                session_id=session_id,
                task_id=tr.task_id,
                l1=result["l1"]["score"],
                l2=result["l2"]["score"],
                l3=result["l3"]["score"],
                composite=composite_info["composite_score"],
                details=result,
            )
        await self.mark_session_scored(session_id)

    async def get_session_status(self, session_id: str) -> SessionResponse:
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        tasks = await self._get_tasks_with_status(session_id)
        return SessionResponse(session_id=session_id, tasks=tasks, status=session.status)

    async def get_trial_data(self, session_id: str, task_id: str) -> list[dict] | None:
        result = await self.db.execute(
            select(TaskResult).where(
                TaskResult.session_id == session_id,
                TaskResult.task_id == task_id,
            )
        )
        task_result = result.scalar_one_or_none()
        if task_result is None:
            return None
        return json.loads(task_result.trial_data)

    async def get_all_task_results(self, session_id: str) -> list[TaskResult]:
        result = await self.db.execute(
            select(TaskResult).where(TaskResult.session_id == session_id)
        )
        return list(result.scalars().all())

    async def save_score(
        self, session_id: str, task_id: str,
        l1: float, l2: float, l3: float, composite: float, details: dict
    ) -> None:
        existing = await self.db.execute(
            select(Score).where(Score.session_id == session_id, Score.task_id == task_id)
        )
        old = existing.scalar_one_or_none()
        if old:
            await self.db.delete(old)

        score = Score(
            session_id=session_id,
            task_id=task_id,
            l1_completion=l1,
            l2_accuracy=l2,
            l3_behavioral=l3,
            composite=composite,
            details=json.dumps(details),
        )
        self.db.add(score)
        await self.db.commit()

    async def get_scorecard(self, session_id: str) -> ScorecardResponse:
        result = await self.db.execute(
            select(Score).where(Score.session_id == session_id)
        )
        scores = list(result.scalars().all())

        if not scores:
            raise ValueError(f"No scores found for session {session_id}")

        task_scores = []
        for s in scores:
            task_scores.append(TaskScore(
                task_id=s.task_id,
                l1_completion=s.l1_completion,
                l2_accuracy=s.l2_accuracy,
                l3_behavioral=s.l3_behavioral,
                composite=s.composite,
                details=json.loads(s.details) if s.details else None,
            ))

        n = len(task_scores)
        return ScorecardResponse(
            session_id=session_id,
            task_scores=task_scores,
            composite_score=round(sum(t.composite for t in task_scores) / n, 2),
            l1_overall=round(sum(t.l1_completion for t in task_scores) / n, 4),
            l2_overall=round(sum(t.l2_accuracy for t in task_scores) / n, 4),
            l3_overall=round(sum(t.l3_behavioral for t in task_scores) / n, 4),
        )

    async def mark_session_scored(self, session_id: str) -> None:
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.status = "scored"
            await self.db.commit()

    async def get_leaderboard(self) -> list[dict]:
        result = await self.db.execute(
            select(Session).where(Session.status == "scored")
        )
        sessions = list(result.scalars().all())

        entries = []
        for session in sessions:
            scores_result = await self.db.execute(
                select(Score).where(Score.session_id == session.id)
            )
            scores = list(scores_result.scalars().all())
            if not scores:
                continue

            n = len(scores)
            entries.append({
                "session_id": session.id,
                "agent_name": session.agent_name,
                "scaffold": session.scaffold,
                "model_name": session.model_name,
                "observation_mode": session.observation_mode,
                "composite_score": round(sum(s.composite for s in scores) / n, 2),
                "l1_overall": round(sum(s.l1_completion for s in scores) / n, 4),
                "l2_overall": round(sum(s.l2_accuracy for s in scores) / n, 4),
                "l3_overall": round(sum(s.l3_behavioral for s in scores) / n, 4),
                "tasks_completed": n,
                "evaluated_at": session.updated_at.isoformat() if session.updated_at else None,
            })

        entries.sort(key=lambda e: e["composite_score"], reverse=True)
        return entries
