import json
import logging
import uuid
from statistics import fmean
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from harness.config import settings
from harness.db.models import (
    Session, TaskResult, Score,
    SessionCreate, SessionResponse, TaskInfo, TaskScore, ScorecardResponse,
)
from harness.task_sets import V1_TASK_IDS
from scoring.score_session import score_task
from scoring.version import LEGACY_VERSION, scorer_version

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
        self, session_id: str, task_id: str, trial_data: list[dict],
        metadata: dict | None = None, is_complete: bool = True,
    ) -> None:
        await self.validate_session_active(session_id)

        result = await self.db.execute(
            select(TaskResult).where(
                TaskResult.session_id == session_id,
                TaskResult.task_id == task_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing_len = len(json.loads(existing.trial_data))
            if is_complete or len(trial_data) >= existing_len:
                existing.trial_data = json.dumps(trial_data)
                existing.is_complete = is_complete
                existing.submitted_at = datetime.now(timezone.utc)
        else:
            task_result = TaskResult(
                session_id=session_id,
                task_id=task_id,
                trial_data=json.dumps(trial_data),
                is_complete=is_complete,
            )
            self.db.add(task_result)

        sess_result = await self.db.execute(select(Session).where(Session.id == session_id))
        session = sess_result.scalar_one_or_none()
        # validate_session_active above already 400s on status == "scored",
        # so we can unconditionally set in_progress here.
        if session:
            session.status = "in_progress"
        await self.db.commit()

        if is_complete:
            await self._auto_evaluate_if_complete(session_id)

    async def _auto_evaluate_if_complete(self, session_id: str) -> None:
        """Score once the v1 launch set has been submitted.

        The gate used to be every task directory on disk — 50-plus — which
        nothing runs end to end. The reference harness never noticed because it
        POSTs /api/evaluate itself, but skill.md is the public submission guide
        and no longer carries that instruction, so a browser-only agent that
        completed the ten advertised tasks was left `in_progress` with no Score
        rows and never reached the leaderboard.

        Scoring after *each* task is not the alternative: `validate_session_active`
        rejects submissions to a session whose status is "scored", so closing the
        session on the first task would 400 every task after it. The gate has to
        stay all-or-nothing; it just has to be all of a set someone actually
        completes. Agents submitting a different subset call /api/evaluate
        explicitly, which skill.md documents.

        There is deliberately no "else fall back to every task on disk" clause:
        that is the 50-task gate this replaced, and re-enabling it whenever a
        deployment happens not to ship the v1 set would reintroduce the bug
        inside the function written to remove it. A deployment without the v1
        tasks simply does not auto-evaluate, and the explicit POST still works.
        """
        submitted = await self.db.execute(
            select(TaskResult.task_id).where(TaskResult.session_id == session_id)
        )
        submitted_ids = set(submitted.scalars().all())
        # Cheap test first: this runs on every completed task submission, and
        # returns here for all but the last, so scanning tasks/ (~100 stat
        # syscalls) before the early return was pure waste 9 times in 10.
        if not V1_TASK_IDS <= submitted_ids:
            return

        logger.info("v1 set complete for session %s (%d tasks submitted) — auto-evaluating",
                    session_id, len(submitted_ids))
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
        """Persist one task's score, keyed by (session, task, scorer version).

        Re-scoring under the SAME version replaces the row, so repeated
        evaluation stays idempotent. Re-scoring under a NEW version inserts
        alongside, so the older numbers survive and stay selectable on the
        leaderboard instead of being silently overwritten by a scorer change.

        The version is resolved here rather than passed in by callers: two of
        the three write paths (browser-driven auto-evaluation, and the in-page
        POST to /api/evaluate) never involve a harness process, so anything
        computed at the CLI layer would leave them blank.
        """
        version = details.get("scorer_version") or scorer_version()

        existing = await self.db.execute(
            select(Score).where(Score.session_id == session_id,
                                Score.task_id == task_id,
                                Score.scorer_version == version)
        )
        for old in existing.scalars().all():
            await self.db.delete(old)

        score = Score(
            session_id=session_id,
            task_id=task_id,
            l1_completion=l1,
            l2_accuracy=l2,
            l3_behavioral=l3,
            composite=composite,
            details=json.dumps(details),
            scorer_version=version,
            spec_digest=details.get("spec_digest"),
        )
        self.db.add(score)
        await self.db.commit()

    @staticmethod
    def _newest_version(scores) -> str | None:
        """The version whose most recent row is newest, over `scores`.

        LEGACY_VERSION loses every tie, so a real version always wins over rows
        whose provenance was never recorded.
        """
        latest: dict[str, datetime] = {}
        for s in scores:
            v = s.scorer_version or LEGACY_VERSION
            when = s.scored_at or datetime.min
            if v not in latest or when > latest[v]:
                latest[v] = when
        if not latest:
            return None
        return max(latest, key=lambda v: (latest[v], v != LEGACY_VERSION))

    @classmethod
    def _newest_generation(cls, scores):
        """The subset of `scores` written by the newest version present."""
        return cls._at_version(scores, cls._newest_version(scores))

    @staticmethod
    def _at_version(scores, version: str | None):
        if version is None:
            return list(scores)
        return [s for s in scores if (s.scorer_version or LEGACY_VERSION) == version]

    async def get_scorecard(self, session_id: str,
                            scorer_version_filter: str | None = None) -> ScorecardResponse:
        result = await self.db.execute(
            select(Score).where(Score.session_id == session_id)
        )
        scores = list(result.scalars().all())

        if not scores:
            raise ValueError(f"No scores found for session {session_id}")

        # A session re-scored under a new version holds several rows per task.
        # Averaging across them would divide by the wrong n and report a
        # composite belonging to no scorer version at all. Default to the
        # newest version present for THIS session, so a session that was never
        # re-scored renders exactly as before.
        scores = (self._at_version(scores, scorer_version_filter)
                  if scorer_version_filter else self._newest_generation(scores))

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

    async def list_scorer_versions(self) -> list[dict]:
        """Every scorer version with approved, scored rows behind it, newest first.

        Drives the leaderboard's version selector. Built from the DATA rather
        than from the running code, so it never offers a version with nothing to
        show, and never hides one that exists.

        An aggregate rather than a row scan: the previous form loaded every
        approved Session and every Score through the ORM — including the ~2 KB
        `details` blob per row that nothing here reads — to compute five scalars
        per version.
        """
        version = func.coalesce(Score.scorer_version, LEGACY_VERSION)
        result = await self.db.execute(
            select(version,
                   func.count(func.distinct(Score.session_id)),
                   func.count(),
                   func.min(Score.scored_at),
                   func.max(Score.scored_at))
            .join(Session, Score.session_id == Session.id)
            .where(Session.status == "scored", Session.approved == True)  # noqa: E712
            .group_by(version)
        )
        rows = [
            {"version": v, "sessions": n_sessions, "scores": n_scores,
             "first_scored_at": first, "last_scored_at": last,
             "is_legacy": v == LEGACY_VERSION}
            for v, n_sessions, n_scores, first, last in result.all()
        ]
        # Newest activity first, on the datetime rather than its serialization.
        # Legacy loses ties, so a real version always leads.
        rows.sort(key=lambda r: (r["last_scored_at"] or datetime.min, not r["is_legacy"]),
                  reverse=True)
        for r in rows:
            for key in ("first_scored_at", "last_scored_at"):
                r[key] = r[key].isoformat() if r[key] else None
        return rows

    async def get_leaderboard(self, task_ids: set[str] | None = None,
                              scorer_version_filter: str | None = None) -> list[dict]:
        """Ranked table of approved, scored sessions.

        ``scorer_version_filter`` restricts to one scorer version. Mixing
        versions in one column would report a composite belonging to no scorer
        at all, which is the failure the version selector exists to prevent, so
        there is deliberately no "all versions" option.

        ``task_ids`` restricts the board to one task set; the routes pass the v1
        launch set so the leaderboard is scored over the same ten tasks the rest
        of the site shows. Without it, entries evaluated on different subsets of
        the catalogue get ranked against each other in one composite column,
        which compares a 35-task mean with a 7-task mean.

        Repeats of the same (model, task) are AVERAGED, not maxed. Keeping the
        best of N rewards the luckiest draw and grows with the number of attempts
        a submitter makes: on the ten-repeat study, best-of-ten runs 14 to 18
        composite points above the mean. Averaging within a task before averaging
        across tasks also keeps every task equally weighted when repeat counts
        are uneven.
        """
        result = await self.db.execute(
            select(Session)
            .where(Session.status == "scored", Session.approved == True)  # noqa: E712
            .options(selectinload(Session.scores))
        )
        sessions = list(result.scalars().all())

        grouped: dict[tuple[str, str], dict] = {}
        for session in sessions:
            if not session.scores:
                continue

            # Observation mode is part of the identity of an evaluated system,
            # not a property of it. Without it in the key, the vision ablation's
            # DOM-only runs merge into the same row as that model's screenshot
            # runs and drag its composite toward the ablated condition — two
            # different agents reported as one.
            key = (session.model_name, session.scaffold, session.observation_mode)
            if key not in grouped:
                grouped[key] = {
                    "agent_name": session.agent_name,
                    "scaffold": session.scaffold,
                    "model_name": session.model_name,
                    "observation_mode": session.observation_mode,
                    "by_task": {},
                    "latest_at": session.updated_at,
                }
            group = grouped[key]
            for score in session.scores:
                if task_ids is not None and score.task_id not in task_ids:
                    continue
                if scorer_version_filter is not None and not self._at_version(
                    [score], scorer_version_filter
                ):
                    continue
                group["by_task"].setdefault(score.task_id, []).append(score)
            if session.updated_at and (
                group["latest_at"] is None
                or session.updated_at > group["latest_at"]
            ):
                group["latest_at"] = session.updated_at

        entries = []
        for group in grouped.values():
            by_task = group["by_task"]
            if not by_task:
                continue  # nothing in the requested task set

            def level(attr, by_task=by_task):
                """Mean within each task, then across tasks."""
                return fmean([fmean([getattr(s, attr) for s in rows])
                              for rows in by_task.values()])

            entries.append({
                "agent_name": group["agent_name"],
                "scaffold": group["scaffold"],
                "model_name": group["model_name"],
                "observation_mode": group["observation_mode"],
                "composite_score": round(level("composite"), 2),
                "l1_overall": round(level("l1_completion"), 4),
                "l2_overall": round(level("l2_accuracy"), 4),
                "l3_overall": round(level("l3_behavioral"), 4),
                "tasks_completed": len(by_task),
                "sessions_scored": sum(len(v) for v in by_task.values()),
                "evaluated_at": group["latest_at"].isoformat() if group["latest_at"] else None,
            })

        entries.sort(key=lambda e: e["composite_score"], reverse=True)
        return entries

    async def get_submissions(self, status_filter: str | None = None) -> list[dict]:  # "pending"|"approved"|"rejected"
        """Return all scored sessions with approval status for admin review."""
        query = select(Session).where(Session.status == "scored").options(selectinload(Session.scores))
        if status_filter == "pending":
            query = query.where(Session.approved.is_(None))
        elif status_filter == "approved":
            query = query.where(Session.approved == True)  # noqa: E712
        elif status_filter == "rejected":
            query = query.where(Session.approved == False)  # noqa: E712

        result = await self.db.execute(query.order_by(Session.created_at.desc()))
        sessions = list(result.scalars().all())

        entries = []
        for session in sessions:
            # One version at a time, else a re-scored session's means divide by
            # a doubled n. Newest per session, matching get_scorecard.
            scores = self._newest_generation(session.scores)
            n = len(scores) if scores else 0
            entries.append({
                "session_id": session.id,
                "agent_name": session.agent_name,
                "scaffold": session.scaffold,
                "model_name": session.model_name,
                "composite_score": round(sum(s.composite for s in scores) / n, 2) if n else 0,
                "l1_overall": round(sum(s.l1_completion for s in scores) / n, 4) if n else 0,
                "l2_overall": round(sum(s.l2_accuracy for s in scores) / n, 4) if n else 0,
                "l3_overall": round(sum(s.l3_behavioral for s in scores) / n, 4) if n else 0,
                "tasks_completed": n,
                "approved": session.approved,
                "reviewed_by": session.reviewed_by,
                "review_notes": session.review_notes,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "reviewed_at": session.reviewed_at.isoformat() if session.reviewed_at else None,
            })
        return entries

    async def _set_review_status(self, session_id: str, approved: bool, reviewed_by: str | None = None, notes: str | None = None) -> dict:
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session.approved = approved
        session.reviewed_by = reviewed_by
        session.review_notes = notes
        session.reviewed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return {"session_id": session_id, "approved": approved}

    async def approve_session(self, session_id: str, reviewed_by: str | None = None, notes: str | None = None) -> dict:
        return await self._set_review_status(session_id, True, reviewed_by, notes)

    async def reject_session(self, session_id: str, reviewed_by: str | None = None, notes: str | None = None) -> dict:
        return await self._set_review_status(session_id, False, reviewed_by, notes)
