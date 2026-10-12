#!/usr/bin/env python3
"""
Continuous backlog runner: processes pending/error episodes newest-first until none remain.

Rate-limit handling: after any failure, sleeps with exponential backoff (60s doubling to 30min),
resetting on success. Single instance enforced via a lock file.

Usage:
    python3 backlog_runner.py
"""

import fcntl
import logging
import sys
import time

from google import genai

from batch_processor import ROOT, get_next_api_key, init_db, process_episode, update_episode_status
from daily_processor import find_backfill_episode

LOCK_PATH = ROOT / "data" / ".backlog_runner.lock"
BACKOFF_START = 60
BACKOFF_MAX = 1800

log = logging.getLogger("backlog")


def main():
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error(f"Another backlog runner holds {LOCK_PATH}; exiting")
        sys.exit(1)

    init_db()
    backoff = BACKOFF_START
    while True:
        ep = find_backfill_episode()
        if not ep:
            log.info("Backlog empty. Done.")
            return

        client = genai.Client(api_key=get_next_api_key())
        try:
            process_episode(client, ep)
        except Exception as e:
            log.error(f"Episode #{ep['episode_number']} failed: {e}")
            update_episode_status(ep["episode_number"], "error", str(e))
            log.info(f"Backing off {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)
        else:
            backoff = BACKOFF_START


if __name__ == "__main__":
    main()
