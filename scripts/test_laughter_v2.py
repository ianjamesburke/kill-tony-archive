"""
Test refined window-based laughter detection.
Fix: stricter scoring rubric to reduce false positives.
Run on both 6-min and 30-min clips.
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

WINDOW_SIZE = 5  # seconds per window

PROMPT = """
Listen to this audio clip from a Kill Tony comedy show. Your job is to detect CROWD REACTIONS ONLY.

The audio is {duration} seconds long. Divide it into {num_windows} consecutive {window_size}-second windows.

For each window, score the CROWD LAUGHTER/APPLAUSE level. Return a JSON array:

[
  {{"w": 0, "s": 0}},
  {{"w": 1, "s": 0}},
  {{"w": 2, "s": 2}},
  ...
]

"w" = window index (0 = first {window_size} seconds, 1 = next {window_size} seconds, etc.)
"s" = crowd reaction score for that window:

  0 = NO crowd reaction. Someone is TALKING (comedian, host, guest) and the audience is QUIET. This is the DEFAULT state. Most of the show is people talking — score those windows 0.
  1 = LIGHT crowd reaction — scattered chuckles, a few people laughing, brief titter
  2 = MODERATE — clear audible laughter from a decent portion of the crowd
  3 = BIG LAUGHS — strong, loud laughter filling the room, or sustained applause
  4 = ROARING — explosive laughter, the entire room erupting, thunderous standing-ovation-level applause

CRITICAL RULES:
- During a comedian's SET (performing jokes), most windows should be 0 (comedian talking) with occasional 1-4 spikes when jokes land.
- During HOST TALKING or INTERVIEWS, most windows should be 0.
- Background noise, murmuring, and ambient crowd sounds are NOT reactions — score them 0.
- Only score > 0 when you hear DISTINCT crowd laughter, applause, cheering, or groaning as a reaction to something said.
- A typical 1-minute comedy set has maybe 3-6 laugh moments, not continuous laughter.
- When in doubt, score LOWER not higher.

Return exactly {num_windows} entries in order. w must go from 0 to {max_window}.
"""


def run_test(client, audio_path, duration, label):
    num_windows = duration // WINDOW_SIZE + (1 if duration % WINDOW_SIZE else 0)
    max_window = num_windows - 1

    prompt = PROMPT.format(
        duration=duration,
        num_windows=num_windows,
        window_size=WINDOW_SIZE,
        max_window=max_window,
    )

    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Duration: {duration}s, Windows: {num_windows} × {WINDOW_SIZE}s")
    print(f"{'='*60}")

    uploaded = client.files.upload(file=audio_path)
    try:
        for _ in range(120):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        t0 = time.time()
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt, uploaded],
            config={
                "response_mime_type": "application/json",
                "http_options": {"timeout": 600000},
            },
        )
        elapsed = time.time() - t0
        raw = (response.text or "").strip()
        windows = json.loads(raw)
        print(f"Response in {elapsed:.1f}s, {len(windows)} windows returned")
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    # Convert to per-second timeline
    timeline = [0] * duration
    for w in windows:
        idx = w.get("w", 0)
        score = w.get("s", 0)
        start = idx * WINDOW_SIZE
        for s in range(start, min(start + WINDOW_SIZE, duration)):
            timeline[s] = score

    # Display
    chars = {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}
    minutes = (duration + 59) // 60
    for m in range(minutes):
        start = m * 60
        end = min(start + 60, duration)
        bar = "".join(chars.get(timeline[s], "?") for s in range(start, end))
        print(f"  {m:2d}:00 |{bar}|")
    print(f"  Legend: · silence  ░ light  ▒ moderate  ▓ big  █ roaring")

    active = sum(1 for s in timeline if s > 0)
    silent = sum(1 for s in timeline if s == 0)
    print(f"\n  Active: {active}s ({active/duration*100:.1f}%) | Silent: {silent}s ({silent/duration*100:.1f}%)")
    print(f"  Expected {num_windows} windows, got {len(windows)} {'✓' if len(windows) == num_windows else '✗'}")

    # Score distribution
    scores = [w.get("s", 0) for w in windows]
    for level in range(5):
        count = scores.count(level)
        print(f"  Score {level}: {count} windows ({count/len(scores)*100:.0f}%)")

    return {
        "label": label,
        "duration": duration,
        "elapsed": elapsed,
        "num_windows": len(windows),
        "expected_windows": num_windows,
        "timeline": timeline,
        "raw_windows": windows,
        "active_pct": active / duration * 100,
    }


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    results = []

    # Test 1: 6-minute clip
    clip_path = Path(__file__).parent / "test_clip.mp3"
    if clip_path.exists():
        r = run_test(client, clip_path, 365, "6-min clip (ep 539 bucket pull)")
        results.append(r)
        time.sleep(10)

    # Test 2: 30-minute chunk
    long_path = Path(__file__).parent / "test_30min.mp3"
    if long_path.exists():
        r = run_test(client, long_path, 1800, "30-min chunk (ep 738 first half)")
        results.append(r)

    # Save
    out = Path(__file__).parent / "test_laughter_v2_results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
