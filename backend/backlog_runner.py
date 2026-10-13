#!/usr/bin/env python3
"""
Continuous backlog runner: processes pending/error episodes newest-first until none remain.

Run N workers in parallel with distinct worker ids; episodes are claimed atomically in the DB.

Rate-limit handling: after any failure, sleeps with exponential backoff (60s doubling to 30min),
resetting on success. One instance per worker id enforced via a lock file.

Usage:
    python3 backlog_runner.py <worker_id> [--provider gemini|openrouter] [--limit N]
"""

import argparse
import fcntl
import logging
import sqlite3
import sys
import time

from google import genai

import batch_processor
from batch_processor import DB_PATH, ROOT, get_next_api_key, init_db, process_episode, update_episode_status
from daily_processor import find_backfill_episode

BACKOFF_START = 60
BACKOFF_MAX = 1800

log = logging.getLogger("backlog")


def claim(ep_num: int) -> bool:
    """Atomically move an episode to 'processing'; False if another worker got it first."""
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute(
            "UPDATE episodes SET status = 'processing' WHERE episode_number = ? AND status IN ('pending', 'error')",
            (ep_num,),
        )
    return cur.rowcount == 1


def main(worker_id: str, limit: int | None):
    lock_path = ROOT / "data" / f".backlog_runner_{worker_id}.lock"
    lock = open(lock_path, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error(f"Another backlog runner holds {lock_path}; exiting")
        sys.exit(1)

    init_db()
    backoff = BACKOFF_START
    attempted = 0
    while limit is None or attempted < limit:
        ep = find_backfill_episode()
        if not ep:
            log.info("Backlog empty. Done.")
            return
        if not claim(ep["episode_number"]):
            continue

        attempted += 1
        client = genai.Client(api_key=get_next_api_key())
        try:
            process_episode(client, ep, skip_laughter=True)
        except Exception as e:
            log.error(f"Episode #{ep['episode_number']} failed: {e}")
            if "PerDay" in str(e):
                # Daily quota exhaustion on this key says nothing about the episode; requeue without counting it.
                update_episode_status(ep["episode_number"], "pending")
            else:
                update_episode_status(ep["episode_number"], "error", str(e))
            log.info(f"Backing off {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)
        else:
            backoff = BACKOFF_START


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("worker_id")
    parser.add_argument("--provider", choices=["gemini", "openrouter"], default="gemini")
    parser.add_argument("--limit", type=int, help="Stop after attempting this many episodes")
    args = parser.parse_args()
    batch_processor.PASS2_PROVIDER = args.provider
    main(args.worker_id, args.limit)
