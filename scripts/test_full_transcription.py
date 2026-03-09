"""
Test: Full-episode single-shot Pass 1 transcription via Gemini 3 Flash.
Validates that timestamps are clean and sequential on a full 2h+ episode.
"""
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))
from batch_processor import PASS1_PROMPT_FULL, normalize_speaker

AUDIO_PATH = Path(__file__).parent / "ep738_full.mp3"
DURATION = 8631


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print(f"Uploading {AUDIO_PATH.name} ({AUDIO_PATH.stat().st_size / 1024 / 1024:.1f} MB)...")
    uploaded = client.files.upload(file=AUDIO_PATH)

    try:
        print("Waiting for file to become active...")
        for _ in range(300):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        print(f"File active. Sending full-episode transcription prompt...")
        t0 = time.time()

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[PASS1_PROMPT_FULL, uploaded],
            config={"http_options": {"timeout": 600000}},
        )
        elapsed = time.time() - t0
        print(f"Response in {elapsed:.1f}s")

        raw = (response.text or "").strip()

        # Strip markdown fences if present
        import re
        if "```" in raw:
            raw = re.sub(r"```(?:json)?", "", raw).strip()

        entries = json.loads(raw)
        print(f"Got {len(entries)} transcript entries")
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    # Normalize speakers
    for entry in entries:
        entry["speaker"] = normalize_speaker(entry.get("speaker", "unknown"))

    # Validate timestamps
    timestamps = [e.get("start_seconds", 0) for e in entries]
    max_ts = max(timestamps) if timestamps else 0
    min_ts = min(timestamps) if timestamps else 0

    print(f"\n{'='*60}")
    print(f"TRANSCRIPT QUALITY REPORT")
    print(f"{'='*60}")
    print(f"Entries: {len(entries)}")
    print(f"Time range: {min_ts:.0f}s - {max_ts:.0f}s ({max_ts/60:.1f} min)")
    print(f"Episode duration: {DURATION}s ({DURATION/60:.1f} min)")
    print(f"Coverage: {max_ts/DURATION*100:.1f}%")
    print(f"API response time: {elapsed:.1f}s")

    # Check for monotonic timestamps
    non_monotonic = 0
    for i in range(1, len(entries)):
        if entries[i].get("start_seconds", 0) < entries[i-1].get("start_seconds", 0):
            non_monotonic += 1
    print(f"Non-monotonic timestamps: {non_monotonic}")

    # Check for large gaps
    large_gaps = []
    for i in range(1, len(entries)):
        gap = entries[i].get("start_seconds", 0) - entries[i-1].get("end_seconds", entries[i-1].get("start_seconds", 0))
        if gap > 30:
            large_gaps.append({
                "after_entry": i-1,
                "gap_seconds": gap,
                "from": entries[i-1].get("end_seconds", 0),
                "to": entries[i].get("start_seconds", 0),
            })
    print(f"Gaps > 30s: {len(large_gaps)}")
    for g in large_gaps[:10]:
        print(f"  {g['from']/60:.1f}min - {g['to']/60:.1f}min ({g['gap_seconds']:.0f}s gap)")

    # Speaker distribution
    speakers = {}
    for e in entries:
        s = e.get("speaker", "unknown")
        speakers[s] = speakers.get(s, 0) + 1

    print(f"\nSpeaker distribution:")
    for s, count in sorted(speakers.items(), key=lambda x: -x[1])[:20]:
        print(f"  {s}: {count} entries")

    # Show first 20 entries
    print(f"\nFirst 20 entries:")
    for e in entries[:20]:
        ts = e.get("start_seconds", 0)
        print(f"  [{int(ts//60):02d}:{int(ts%60):02d}] {e.get('speaker', '?')}: {e.get('text', '')[:80]}")

    # Show entries around 37:17 (Olivia equivalent — some set boundary)
    print(f"\nEntries around 37:00 (sample set boundary check):")
    for e in entries:
        ts = e.get("start_seconds", 0)
        if 2200 <= ts <= 2280:
            print(f"  [{int(ts//60):02d}:{int(ts%60):02d}] {e.get('speaker', '?')}: {e.get('text', '')[:80]}")

    # Show last 10 entries
    print(f"\nLast 10 entries:")
    for e in entries[-10:]:
        ts = e.get("start_seconds", 0)
        print(f"  [{int(ts//60):02d}:{int(ts%60):02d}] {e.get('speaker', '?')}: {e.get('text', '')[:80]}")

    # Save
    out = Path(__file__).parent / "test_full_transcript_ep738.json"
    with open(out, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"\nSaved {len(entries)} entries to {out}")


if __name__ == "__main__":
    main()
