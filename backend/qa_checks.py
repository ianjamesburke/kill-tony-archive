"""
Post-processing QA checks for Kill Tony episode pipeline.

Two checks:
1. Set count validation — flag episodes with fewer than expected sets
2. Timecode spot-check — sample a set, extract a short audio clip at set_start_seconds,
   send to Gemini, verify the transcript matches

Usage:
    # Run as standalone on already-processed episodes:
    python3 qa_checks.py --episode 761
    python3 qa_checks.py --all          # Check all "done" episodes
    python3 qa_checks.py --fix 761      # Re-run Pass 2 on flagged episode

    # Called from process_episode() as post-processing step
"""

import json
import logging
import os
import random
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

from google import genai
from batch_processor import (
    DB_PATH,
    AUDIO_CACHE_DIR,
    GUEST_MODEL,
    download_audio,
    update_episode_status,
    rate_limit,
    upload_and_wait,
)

log = logging.getLogger("qa")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MIN_SETS_EXPECTED = 8       # Most episodes have 10-15 sets. Flag below this.
TIMECODE_CLIP_SECONDS = 15  # Extract this many seconds of audio for spot-check
SIMILARITY_THRESHOLD = 0.3  # Word overlap threshold to consider a match
QA_MODEL = GUEST_MODEL      # Use the cheap model for QA checks


# ---------------------------------------------------------------------------
# Set count check
# ---------------------------------------------------------------------------

def check_set_count(episode_number: int) -> dict:
    """Check if an episode has a reasonable number of sets."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM sets WHERE episode_number = ?",
            (episode_number,)
        ).fetchone()
        set_count = row[0] if row else 0

    passed = set_count >= MIN_SETS_EXPECTED
    result = {
        "check": "set_count",
        "episode": episode_number,
        "set_count": set_count,
        "min_expected": MIN_SETS_EXPECTED,
        "passed": passed,
    }
    if not passed:
        result["warning"] = f"Only {set_count} sets found (expected >= {MIN_SETS_EXPECTED}). Pass 2 may have missed sets."
    return result


# ---------------------------------------------------------------------------
# Timecode spot-check
# ---------------------------------------------------------------------------

def _extract_clip(audio_path: Path, start_seconds: float, duration: int = TIMECODE_CLIP_SECONDS) -> Path:
    """Extract a short clip from the full audio file using ffmpeg."""
    clip_path = Path(tempfile.mktemp(suffix=".mp3"))
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(int(start_seconds)),
            "-i", str(audio_path),
            "-t", str(duration),
            "-q:a", "5",
            str(clip_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    return clip_path


def _word_overlap(text_a: str, text_b: str) -> float:
    """Calculate word overlap between two texts (0.0-1.0)."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))


def check_timecode(client: genai.Client, episode_number: int, audio_path: Path, set_to_check: dict | None = None) -> dict:
    """Spot-check a set's timecode by transcribing a short audio clip and comparing.

    If set_to_check is None, picks a random set from the episode.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT set_number, comedian_name, set_start_seconds, set_transcript "
            "FROM sets WHERE episode_number = ? ORDER BY set_number",
            (episode_number,)
        ).fetchall()

    if not rows:
        return {
            "check": "timecode",
            "episode": episode_number,
            "passed": False,
            "warning": "No sets found in database",
        }

    sets = [dict(r) for r in rows]

    if set_to_check:
        target = set_to_check
    else:
        # Pick a random set (prefer middle sets — they're most likely to have alignment issues)
        if len(sets) > 2:
            target = random.choice(sets[1:-1])
        else:
            target = random.choice(sets)

    start = target["set_start_seconds"]
    if not start or start <= 0:
        return {
            "check": "timecode",
            "episode": episode_number,
            "set_number": target["set_number"],
            "passed": False,
            "warning": f"Set #{target['set_number']} has invalid start time: {start}",
        }

    # Extract clip
    try:
        clip_path = _extract_clip(audio_path, start)
    except Exception as e:
        return {
            "check": "timecode",
            "episode": episode_number,
            "set_number": target["set_number"],
            "passed": False,
            "warning": f"Failed to extract audio clip: {e}",
        }

    try:
        # Upload and transcribe clip
        uploaded = upload_and_wait(client, clip_path)
        try:
            response = client.models.generate_content(
                model=QA_MODEL,
                contents=[
                    "Transcribe the first 10 seconds of this audio clip. "
                    "Return ONLY the spoken words, no timestamps, no speaker labels, no commentary.",
                    uploaded,
                ],
                config={"http_options": {"timeout": 60000}},
            )
            clip_text = (response.text or "").strip()
        finally:
            try:
                client.files.delete(name=uploaded.name or "")
            except Exception:
                pass

        rate_limit()

        # Compare with stored transcript
        transcript_start = (target["set_transcript"] or "")[:200]  # First 200 chars
        similarity = _word_overlap(clip_text, transcript_start)

        passed = similarity >= SIMILARITY_THRESHOLD
        result = {
            "check": "timecode",
            "episode": episode_number,
            "set_number": target["set_number"],
            "comedian": target["comedian_name"],
            "start_seconds": start,
            "similarity": round(similarity, 3),
            "passed": passed,
            "clip_transcription": clip_text[:200],
            "expected_start": transcript_start[:200],
        }
        if not passed:
            result["warning"] = (
                f"Timecode mismatch for set #{target['set_number']} ({target['comedian_name']}) "
                f"at {start:.0f}s. Similarity: {similarity:.1%}. "
                f"Audio says: '{clip_text[:80]}...' but transcript starts: '{transcript_start[:80]}...'"
            )
        return result

    finally:
        clip_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Combined QA runner
# ---------------------------------------------------------------------------

def run_qa_checks(
    client: genai.Client,
    episode_number: int,
    audio_path: Path | None = None,
    skip_timecode: bool = False,
) -> list[dict]:
    """Run all QA checks for an episode. Returns list of check results."""
    results = []

    # 1. Set count check (always runs — no API call needed)
    count_result = check_set_count(episode_number)
    results.append(count_result)
    if count_result["passed"]:
        log.info(f"QA set_count: PASS ({count_result['set_count']} sets)")
    else:
        log.warning(f"QA set_count: FAIL — {count_result['warning']}")

    # 2. Timecode spot-check (requires audio file)
    if not skip_timecode and audio_path and audio_path.exists():
        tc_result = check_timecode(client, episode_number, audio_path)
        results.append(tc_result)
        if tc_result["passed"]:
            log.info(
                f"QA timecode: PASS — set #{tc_result.get('set_number')} "
                f"({tc_result.get('comedian')}) at {tc_result.get('start_seconds', 0):.0f}s, "
                f"similarity={tc_result.get('similarity', 0):.1%}"
            )
        else:
            log.warning(f"QA timecode: FAIL — {tc_result.get('warning', 'unknown')}")
    elif not skip_timecode:
        log.info("QA timecode: SKIPPED (no audio file available)")

    return results


def save_qa_results(episode_number: int, results: list[dict]):
    """Save QA results to a JSON file for later review."""
    qa_dir = ROOT / "data" / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    qa_file = qa_dir / f"ep_{episode_number}_qa.json"
    qa_file.write_text(json.dumps(results, indent=2))
    log.info(f"QA results saved to {qa_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Kill Tony QA checks")
    parser.add_argument("--episode", type=int, help="Check a specific episode")
    parser.add_argument("--all", action="store_true", help="Check all done episodes")
    parser.add_argument("--set-count-only", action="store_true", help="Skip timecode check (fast)")
    args = parser.parse_args()

    client = genai.Client()

    if args.episode:
        episodes = [args.episode]
    elif args.all:
        with sqlite3.connect(DB_PATH) as conn:
            episodes = [
                r[0] for r in conn.execute(
                    "SELECT episode_number FROM episodes WHERE status = 'done' ORDER BY episode_number"
                ).fetchall()
            ]
    else:
        parser.print_help()
        exit(1)

    failures = []
    for ep_num in episodes:
        log.info(f"--- QA: Episode #{ep_num} ---")

        # Try to find audio (may have been cleaned up)
        audio_path = AUDIO_CACHE_DIR / f"ep_{ep_num}" / "full.mp3"
        if not audio_path.exists():
            audio_path = None

        results = run_qa_checks(
            client, ep_num,
            audio_path=audio_path,
            skip_timecode=args.set_count_only,
        )
        save_qa_results(ep_num, results)

        for r in results:
            if not r["passed"]:
                failures.append(r)

    if failures:
        log.warning(f"\n{'='*60}")
        log.warning(f"QA FAILURES: {len(failures)}")
        for f in failures:
            log.warning(f"  Ep #{f['episode']}: {f.get('warning', 'unknown')}")
    else:
        log.info(f"\nAll QA checks passed for {len(episodes)} episode(s)")
