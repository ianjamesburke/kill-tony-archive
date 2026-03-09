"""
Test: Can Gemini detect laughter timing from audio?
Uses a short Kill Tony clip to extract laughter timestamps.
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

AUDIO_PATH = Path(__file__).parent / "test_clip.mp3"

PROMPT_TRANSCRIPT = """
Transcribe this Kill Tony clip. For EVERY moment of crowd reaction, log it precisely.

Return a JSON array of entries:
[
  {"start_seconds": 0.0, "end_seconds": 2.5, "speaker": "tony", "text": "..."},
  {"start_seconds": 2.5, "end_seconds": 4.0, "speaker": "crowd", "text": "[laughter]"},
  ...
]

Speaker labels:
- "tony" — Tony Hinchcliffe
- "comedian:<name>" — the performing comedian
- "crowd" — audience reactions: [laughter], [applause], [cheering], [groaning]
- "band" — music
- "guest:<name>" — guest panelists
- "redban" — Brian Redban
- "unknown" — unidentified

CRITICAL: Be very precise about crowd laughter timing. Log EVERY laugh, even brief ones.
Each [laughter] entry should have accurate start/end timestamps.
"""

PROMPT_LAUGHTER_ONLY = """
Listen to this Kill Tony clip and identify EVERY instance of crowd laughter, applause, or cheering.

For each crowd reaction, log the precise start and end time in seconds.

Return ONLY a JSON array:
[
  {"start_seconds": 12.5, "end_seconds": 15.0, "type": "laughter", "intensity": "light"},
  {"start_seconds": 22.0, "end_seconds": 24.5, "type": "laughter", "intensity": "big"},
  ...
]

intensity levels: "light" (chuckles/scattered), "moderate" (solid laugh), "big" (big laughs), "roaring" (house comes down)
type: "laughter", "applause", "cheering", "groaning"

Be exhaustive — catch every reaction, even brief ones. Timestamp precision matters.
"""


def run_test(client, prompt, label):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")

    uploaded = client.files.upload(file=AUDIO_PATH)
    try:
        for _ in range(120):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt, uploaded],
            config={"response_mime_type": "application/json", "http_options": {"timeout": 120000}},
        )
        raw = (response.text or "").strip()
        data = json.loads(raw)
        return data
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Test 1: Full transcript with laughter entries
    transcript = run_test(client, PROMPT_TRANSCRIPT, "Full transcript (laughter as crowd entries)")

    crowd_entries = [e for e in transcript if e.get("speaker") == "crowd"]
    print(f"\nTotal entries: {len(transcript)}")
    print(f"Crowd reaction entries: {len(crowd_entries)}")
    print(f"\nCrowd reactions:")
    total_laugh_seconds = 0
    for e in crowd_entries:
        dur = e.get("end_seconds", 0) - e.get("start_seconds", 0)
        total_laugh_seconds += dur
        print(f"  {e['start_seconds']:.1f}s - {e['end_seconds']:.1f}s ({dur:.1f}s): {e.get('text', '?')}")
    print(f"\nTotal crowd reaction time: {total_laugh_seconds:.1f}s / 365s ({total_laugh_seconds/365*100:.1f}%)")

    with open(Path(__file__).parent / "test_results_gemini_transcript.json", "w") as f:
        json.dump(transcript, f, indent=2)

    time.sleep(10)  # rate limit

    # Test 2: Laughter-only detection
    laughter = run_test(client, PROMPT_LAUGHTER_ONLY, "Laughter-only detection (dedicated prompt)")

    print(f"\nTotal laughter events: {len(laughter)}")
    total_laugh_seconds = 0
    for e in laughter:
        dur = e.get("end_seconds", 0) - e.get("start_seconds", 0)
        total_laugh_seconds += dur
        print(f"  {e['start_seconds']:.1f}s - {e['end_seconds']:.1f}s ({dur:.1f}s): {e.get('type', '?')} ({e.get('intensity', '?')})")
    print(f"\nTotal laughter time: {total_laugh_seconds:.1f}s / 365s ({total_laugh_seconds/365*100:.1f}%)")

    with open(Path(__file__).parent / "test_results_gemini_laughter.json", "w") as f:
        json.dump(laughter, f, indent=2)

    print(f"\n{'='*60}")
    print("Results saved to scripts/test_results_gemini_*.json")


if __name__ == "__main__":
    main()
