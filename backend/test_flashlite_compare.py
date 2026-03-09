"""
Compare gemini-3.1-flash-lite-preview against the existing pipeline output.

Tests:
1. Pass 1 (audio transcription) — 1 chunk from ep 757
2. Pass 2 (set extraction) — using existing ep 750 transcript
3. Laughter detection — 1 chunk from ep 757
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

from batch_processor import (
    PASS1_PROMPT,
    PASS2_PROMPT,
    LAUGHTER_PROMPT,
    _parse_json_array,
    upload_and_wait,
    normalize_speaker,
)

LITE_MODEL = "gemini-3.1-flash-lite-preview"

client = genai.Client()


def test_pass1_one_chunk():
    """Transcribe chunk 1 of ep 757 with flash-lite and compare entry count."""
    print("\n" + "=" * 60)
    print("TEST 1: Pass 1 — Audio Transcription (1 chunk)")
    print("=" * 60)

    chunk_path = Path("audio_cache/ep_757/chunk_01_0s.mp3")
    if not chunk_path.exists():
        print(f"SKIP: {chunk_path} not found")
        return

    prompt = PASS1_PROMPT.format(chunk_num=1, offset_seconds=0, offset_str="0:00")
    uploaded = upload_and_wait(client, chunk_path)

    try:
        t0 = time.time()
        response = client.models.generate_content(
            model=LITE_MODEL,
            contents=[prompt, uploaded],
            config={"http_options": {"timeout": 600000}},
        )
        elapsed = time.time() - t0
        entries = _parse_json_array((response.text or "").strip())

        print(f"  Flash-lite: {len(entries)} entries in {elapsed:.1f}s")
        print(f"  (Previous with flash-3: ~200 entries per 20min chunk)")
        print(f"  (Previous with 2.5-flash: ~800 entries per 20min chunk)")

        # Show a few samples
        for e in entries[:5]:
            speaker = normalize_speaker(e.get("speaker", "?"))
            text = e.get("text", "")[:80]
            print(f"    [{e.get('start_seconds', 0):.0f}s] {speaker}: {text}")

        # Save for inspection
        out = ROOT / "data" / "test_flashlite_pass1_chunk1.json"
        json.dump(entries, out.open("w"), indent=2)
        print(f"  Saved to {out}")

    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass


def test_pass2():
    """Run Pass 2 set extraction on ep 750's existing transcript with flash-lite."""
    print("\n" + "=" * 60)
    print("TEST 2: Pass 2 — Set Extraction (ep 750 transcript)")
    print("=" * 60)

    transcript_path = ROOT / "data" / "transcripts" / "ep_750.json"
    if not transcript_path.exists():
        print(f"SKIP: {transcript_path} not found")
        return

    transcript = json.load(transcript_path.open())
    print(f"  Input: {len(transcript)} transcript entries")

    # Build text like pass2_analyze does
    lines = []
    for entry in transcript:
        ts = entry.get("start_seconds", 0)
        speaker = entry.get("speaker", "unknown")
        text = entry.get("text", "")
        lines.append(f"[{int(ts)}s / {int(ts // 60):02d}:{int(ts % 60):02d}] {speaker}: {text}")

    transcript_text = "\n".join(lines)
    prompt = PASS2_PROMPT.format(transcript=transcript_text, episode_number=750)

    t0 = time.time()
    response = client.models.generate_content(
        model=LITE_MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"response_mime_type": "application/json", "http_options": {"timeout": 600000}},
    )
    elapsed = time.time() - t0

    raw_text = (response.text or "").strip()
    data = json.loads(raw_text)
    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    sets = data.get("sets", [])
    print(f"  Flash-lite: {len(sets)} sets extracted in {elapsed:.1f}s")
    print(f"  (Existing in DB: 15 sets)")

    for s in sets:
        name = s.get("comedian_name", "?")
        status = s.get("status", "?")
        topics = s.get("topic_tags", [])
        reaction = s.get("crowd_reaction", "?")
        print(f"    {name} ({status}) — topics: {topics}, reaction: {reaction}")

    # Save
    out = ROOT / "data" / "test_flashlite_pass2_ep750.json"
    json.dump(data, out.open("w"), indent=2)
    print(f"  Saved to {out}")


def test_laughter():
    """Run laughter detection on chunk 1 of ep 757 with flash-lite."""
    print("\n" + "=" * 60)
    print("TEST 3: Laughter Detection (ep 757 chunk 1)")
    print("=" * 60)

    chunk_path = Path("audio_cache/ep_757/chunk_01_0s.mp3")
    if not chunk_path.exists():
        print(f"SKIP: {chunk_path} not found")
        return

    chunk_duration = 20 * 60  # 20 minutes
    prompt = LAUGHTER_PROMPT.format(duration=chunk_duration, duration_min=20)

    uploaded = upload_and_wait(client, chunk_path)
    try:
        t0 = time.time()
        response = client.models.generate_content(
            model=LITE_MODEL,
            contents=[prompt, uploaded],
            config={"response_mime_type": "application/json", "http_options": {"timeout": 600000}},
        )
        elapsed = time.time() - t0

        raw = (response.text or "").strip()
        events = json.loads(raw)
        if isinstance(events, dict):
            events = events.get("events", events.get("laughter_events", [events]))
        if not isinstance(events, list):
            events = [events]

        print(f"  Flash-lite: {len(events)} laughter events in {elapsed:.1f}s")
        for e in events[:10]:
            print(f"    {e}")

        out = ROOT / "data" / "test_flashlite_laughter_chunk1.json"
        json.dump(events, out.open("w"), indent=2)
        print(f"  Saved to {out}")

    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass


if __name__ == "__main__":
    tests = sys.argv[1:] if len(sys.argv) > 1 else ["pass1", "pass2", "laughter"]

    if "pass2" in tests:
        test_pass2()
    if "pass1" in tests:
        test_pass1_one_chunk()
    if "laughter" in tests:
        test_laughter()

    print("\nDone!")
