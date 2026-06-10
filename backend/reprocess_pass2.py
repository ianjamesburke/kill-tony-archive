"""
Re-run Pass 2 (structured set extraction) for an episode using cached Pass 1 transcript.
Skips the expensive audio transcription entirely — just text API calls via the chunked Pass 2.

Usage:
    python3 reprocess_pass2.py 751          # Re-run pass 2 for episode 751
    python3 reprocess_pass2.py 751 --dry    # Show what would change without writing to DB
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from batch_processor import (
    DB_PATH,
    TRANSCRIPTS_DIR,
    API_KEYS,
    compute_kill_score,
    save_episode,
    init_db,
    pass2_analyze,
)


def load_transcript(episode_number: int) -> list[dict]:
    path = TRANSCRIPTS_DIR / f"ep_{episode_number}.json"
    if not path.exists():
        print(f"ERROR: No cached transcript at {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def compare_with_db(episode_number: int, new_analysis: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    old_sets = {
        row["comedian_name"]: dict(row)
        for row in conn.execute("SELECT * FROM sets WHERE episode_number = ?", (episode_number,))
    }

    new_sets = new_analysis.get("sets", [])
    print(f"\n{'='*70}")
    print(f"COMPARISON: Episode #{episode_number}")
    print(f"{'='*70}")
    print(f"Old: {len(old_sets)} sets | New: {len(new_sets)} sets\n")

    for s in new_sets:
        name = s.get("comedian_name", "?")
        new_status = s.get("status", "?")
        new_start = s.get("set_start_seconds", 0)
        new_end = s.get("set_end_seconds", 0)
        duration = new_end - new_start
        kill_score = compute_kill_score(s)

        old = old_sets.get(name)
        if not old:
            for old_name, old_data in old_sets.items():
                if old_name.lower().replace(" ", "") in name.lower().replace(" ", "") or \
                   name.lower().replace(" ", "") in old_name.lower().replace(" ", ""):
                    old = old_data
                    break

        status_marker = ""
        if old:
            old_status = old.get("status", "?")
            if old_status != new_status:
                status_marker = f"  *** CHANGED: {old_status} -> {new_status} ***"

        print(f"  #{s.get('set_number')}: {name} ({new_status}) @ {int(new_start//60)}:{int(new_start%60):02d} ({duration:.0f}s) kill={kill_score:.0f}{status_marker}")
        if s.get("interview_summary"):
            print(f"       Interview: {s['interview_summary'][:100]}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Re-run Pass 2 for an episode")
    parser.add_argument("episode", type=int, help="Episode number to reprocess")
    parser.add_argument("--dry", action="store_true", help="Compare only, don't write to DB")
    args = parser.parse_args()

    if not API_KEYS:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    transcript = load_transcript(args.episode)
    print(f"Loaded cached transcript for ep #{args.episode}: {len(transcript)} entries")

    client = genai.Client(api_key=API_KEYS[0])

    analysis = pass2_analyze(client, transcript, args.episode)

    output_path = ROOT / "data" / f"reprocess_ep{args.episode}_pass2.json"
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"Saved raw output to {output_path}")

    compare_with_db(args.episode, analysis)

    if args.dry:
        print("\n[DRY RUN] No changes written to database.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM episodes WHERE episode_number = ?", (args.episode,)).fetchone()
    conn.close()

    if not row:
        print("ERROR: Episode not found in DB")
        sys.exit(1)

    yt_info = {
        "episode_number": args.episode,
        "video_id": row["video_id"],
        "view_count": row["view_count"],
        "like_count": row["like_count"],
        "comment_count": row["comment_count"],
        "upload_date": row["upload_date"],
    }
    existing_guests = json.loads(row["guests"]) if row["guests"] else []

    init_db()
    save_episode(yt_info, transcript, analysis, existing_guests)
    print(f"\nDatabase updated for episode #{args.episode}")


if __name__ == "__main__":
    main()
