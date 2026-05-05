"""Re-score every approved session on the production server against the
currently-deployed specs.

The CogArena server's POST /api/evaluate/{session_id} endpoint already
overwrites Score rows by virtue of SessionManager.save_score's upsert
pattern; so once Vercel has redeployed with the new spec JSONs, hitting
that endpoint per session is sufficient to make the leaderboard reflect
the audit fixes. No agent re-run needed; trial_data is unchanged.

Usage::

    python -m scripts.rescore_production --base-url https://cog-arena.vercel.app

Auth: ADMIN_API_KEY must be in env or .env (used to list submissions).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

import httpx

logger = logging.getLogger("rescore-prod")


def _load_admin_key() -> str:
    key = os.environ.get("ADMIN_API_KEY", "").strip()
    if key:
        return key
    env_path = ".env"
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("ADMIN_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("ADMIN_API_KEY not set in env or .env")


def _list_session_ids(client: httpx.Client, admin_key: str) -> list[str]:
    """Return every session_id with a stored score on the server."""
    headers = {"X-Admin-Key": admin_key}
    ids: list[str] = []
    for status in ("pending", "approved", "rejected"):
        r = client.get("/api/admin/submissions",
                       params={"status": status, "limit": 200},
                       headers=headers, timeout=30.0)
        if r.status_code != 200:
            logger.warning("admin list (status=%s) HTTP %d: %s", status, r.status_code, r.text[:200])
            continue
        payload = r.json()
        items = payload if isinstance(payload, list) else payload.get("items", payload.get("submissions", []))
        for it in items:
            sid = it.get("session_id")
            if sid:
                ids.append(sid)
    # Dedupe preserving order
    seen = set()
    out = []
    for sid in ids:
        if sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True,
                        help="Target server, e.g. https://cog-arena.vercel.app")
    parser.add_argument("--dry-run", action="store_true",
                        help="List session ids that would be re-evaluated; do not call /api/evaluate.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    admin_key = _load_admin_key()

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        try:
            r = client.get("/api/health")
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("health check failed: %s", e)
            return 1

        ids = _list_session_ids(client, admin_key)
        logger.info("found %d session(s) on %s", len(ids), args.base_url)
        if args.dry_run:
            for sid in ids:
                print(f"  {sid}")
            return 0

        ok = 0
        fail = 0
        for sid in ids:
            try:
                r = client.post(f"/api/evaluate/{sid}", timeout=120.0)
                if r.status_code == 200:
                    ok += 1
                    logger.info("rescored %s", sid)
                else:
                    fail += 1
                    logger.warning("rescored %s: HTTP %d %s", sid, r.status_code, r.text[:200])
            except httpx.HTTPError as e:
                fail += 1
                logger.warning("rescored %s: %s", sid, e)
            time.sleep(0.2)

        logger.info("done: %d / %d re-evaluated", ok, ok + fail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
