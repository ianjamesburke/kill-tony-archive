#!/usr/bin/env python3
"""
Kill Tony episode processor — runs hourly via cron/systemd.

Processes one episode per run. Priority order:
  1. New episode on YouTube not yet in the DB
  2. Newest unprocessed episode (pending/error)
  3. Newest "done" episode with an outdated pipeline version

Usage:
    python3 daily_processor.py              # Normal run
    python3 daily_processor.py --backfill   # Skip YouTube check, just backfill
    python3 daily_processor.py --dry-run    # Show what would be processed, don't run

Schedule (cron): hourly, 8am–midnight Mountain Time
    0 8-23 * * * cd /path/to/backend && python3 daily_processor.py >> /var/log/killtony.log 2>&1
"""

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# Ensure deno is in PATH for yt-dlp JS challenge solving
_deno_bin = Path.home() / ".deno" / "bin"
if _deno_bin.is_dir() and str(_deno_bin) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_deno_bin}:{os.environ.get('PATH', '')}"

from yt_dlp import YoutubeDL

from batch_processor import (
    DB_PATH,
    PIPELINE_VERSION,
    init_db,
    process_episode,
    load_episodes,
    update_episode_status,
    extract_episode_number,
    is_valid_episode,
    _yt_base_opts,
)
from google import genai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHANNEL_URL = "https://www.youtube.com/@KillTony/videos"
# How many recent videos to scan for new episodes
RECENT_VIDEO_COUNT = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("daily")


# ---------------------------------------------------------------------------
# YouTube channel scanning
# ---------------------------------------------------------------------------

def fetch_recent_videos() -> list[dict]:
    """Fetch recent videos from the Kill Tony YouTube channel."""
    opts = {
        "skip_download": True,
        "quiet": True,
        "extract_flat": True,
        "playlist_items": f"1-{RECENT_VIDEO_COUNT}",
        **_yt_base_opts(),
    }
    log.info("Scanning Kill Tony channel for recent uploads...")
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(CHANNEL_URL, download=False)

    if not info or "entries" not in info:
        log.warning("Could not fetch channel videos")
        return []

    videos = []
    for entry in info["entries"]:
        if not entry:
            continue
        title = entry.get("title", "")
        video_id = entry.get("id", "")
        duration = entry.get("duration")
        videos.append({
            "title": title,
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": duration,
        })

    log.info(f"  Found {len(videos)} recent videos")
    return videos


def find_new_episode(videos: list[dict]) -> dict | None:
    """Find a new Kill Tony episode from recent videos that's not already in the DB."""
    with sqlite3.connect(DB_PATH) as conn:
        existing_ids = {row[0] for row in conn.execute("SELECT video_id FROM episodes").fetchall()}

    for video in videos:
        ep_num = extract_episode_number(video["title"])
        if ep_num is None:
            continue

        if video["video_id"] in existing_ids:
            continue

        duration = video.get("duration")
        if not is_valid_episode(video["title"], duration):
            log.info(f"  Skipping non-episode: {video['title']}")
            continue

        log.info(f"  New episode found: #{ep_num} — {video['title']}")
        return {
            "episode_number": ep_num,
            "title": video["title"],
            "url": video["url"],
            "video_id": video["video_id"],
            "status": "pending",
        }

    log.info("  No new episodes on YouTube")
    return None


def add_episode_to_db(ep: dict):
    """Insert a newly discovered episode into the database."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO episodes
               (episode_number, title, youtube_url, video_id, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (ep["episode_number"], ep["title"], ep["url"], ep["video_id"]),
        )
    log.info(f"  Added episode #{ep['episode_number']} to database")


# ---------------------------------------------------------------------------
# Backfill: pick newest episode that needs processing
# ---------------------------------------------------------------------------

def find_backfill_episode() -> dict | None:
    """Find the next episode to process, newest first.

    Priority:
      1. Newest pending/error episode (never processed or previously failed)
      2. Newest done episode with outdated pipeline_version (needs reprocessing)
    """
    episodes = load_episodes()

    # First: newest unprocessed
    unprocessed = sorted(
        [e for e in episodes if e.get("status") in ("pending", "error")],
        key=lambda e: e["episode_number"],
        reverse=True,
    )
    if unprocessed:
        ep = unprocessed[0]
        log.info(f"Backfill: episode #{ep['episode_number']} ({ep['status']}) — {ep.get('title', '(no title)')}")
        return ep

    # Second: newest done episode with outdated pipeline version
    outdated = sorted(
        [e for e in episodes if e.get("status") == "done" and (e.get("pipeline_version") or 0) < PIPELINE_VERSION],
        key=lambda e: e["episode_number"],
        reverse=True,
    )
    if outdated:
        ep = outdated[0]
        log.info(f"Reprocess: episode #{ep['episode_number']} (pipeline v{ep.get('pipeline_version', 0)} → v{PIPELINE_VERSION}) — {ep.get('title', '(no title)')}")
        # Reset status so process_episode treats it as a fresh run
        update_episode_status(ep["episode_number"], "pending")
        ep["status"] = "pending"
        return ep

    log.info("No unprocessed or outdated episodes remaining")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Kill Tony episode processor (runs hourly)")
    parser.add_argument("--backfill", action="store_true", help="Skip YouTube check, just backfill")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without running")
    args = parser.parse_args()

    init_db()

    target = None

    # Step 1: Check YouTube for new episodes (unless --backfill)
    if not args.backfill:
        try:
            videos = fetch_recent_videos()
            target = find_new_episode(videos)
            if target:
                add_episode_to_db(target)
        except Exception as e:
            log.warning(f"YouTube check failed: {e}")
            log.info("Falling back to backfill...")

    # Step 2: If no new episode, backfill (newest unprocessed or outdated)
    if not target:
        target = find_backfill_episode()

    if not target:
        log.info("Nothing to process. All caught up!")
        return

    log.info(f"Target: episode #{target['episode_number']}")

    if args.dry_run:
        log.info("Dry run — would process this episode. Exiting.")
        return

    # Process the episode
    client = genai.Client()
    try:
        process_episode(client, target)
    except Exception as e:
        log.error(f"Episode #{target['episode_number']} failed: {e}")
        update_episode_status(target["episode_number"], "error", str(e))
        sys.exit(1)

    log.info("Processing complete!")


if __name__ == "__main__":
    main()
