"""
Test: 5-second window laughter detection using Pro models on 60 min of ep 738.
Compare Pro quality vs Flash.
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

AUDIO_PATH = Path(__file__).parent / "test_60min.mp3"
DURATION = 3600
WINDOW_SIZE = 5

PROMPT = """
Listen to this audio clip from a Kill Tony comedy show. Your job is to detect CROWD REACTIONS ONLY.

The audio is {duration} seconds long ({duration_min} minutes). Divide it into {num_windows} consecutive {window_size}-second windows.

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

MODELS = [
    "gemini-2.5-pro",
    # "gemini-3.1-pro-preview",  # may not have free tier
]


def run_model(client, model_name):
    num_windows = DURATION // WINDOW_SIZE
    max_window = num_windows - 1

    prompt = PROMPT.format(
        duration=DURATION,
        duration_min=DURATION // 60,
        num_windows=num_windows,
        window_size=WINDOW_SIZE,
        max_window=max_window,
    )

    print(f"\n{'='*60}")
    print(f"MODEL: {model_name}")
    print(f"60 min, {num_windows} windows × {WINDOW_SIZE}s")
    print(f"{'='*60}")

    uploaded = client.files.upload(file=AUDIO_PATH)
    try:
        for _ in range(180):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        print(f"Sending prompt...")
        t0 = time.time()

        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, uploaded],
            config={
                "response_mime_type": "application/json",
                "http_options": {"timeout": 600000},
            },
        )
        elapsed = time.time() - t0
        print(f"Response in {elapsed:.1f}s")

        raw = (response.text or "").strip()
        windows = json.loads(raw)
        print(f"Got {len(windows)} windows (expected {num_windows})")
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    # Build per-second timeline
    timeline = [0] * DURATION
    for w in windows:
        idx = w.get("w", 0)
        score = w.get("s", 0)
        start = idx * WINDOW_SIZE
        for s in range(start, min(start + WINDOW_SIZE, DURATION)):
            timeline[s] = score

    # Display
    chars = {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}
    print(f"\nTimeline:")
    for m in range(DURATION // 60):
        start = m * 60
        bar = "".join(chars.get(timeline[s], "?") for s in range(start, start + 60))
        print(f"  {m:2d}:00 |{bar}|")
    print(f"  Legend: · silence  ░ light  ▒ moderate  ▓ big  █ roaring")

    active = sum(1 for s in timeline if s > 0)
    print(f"\n  Active: {active}s ({active/DURATION*100:.1f}%) | Silent: {DURATION-active}s ({(DURATION-active)/DURATION*100:.1f}%)")
    print(f"  Windows: {len(windows)}/{num_windows} {'✓' if len(windows) == num_windows else '✗'}")

    scores = [w.get("s", 0) for w in windows]
    for level in range(5):
        count = scores.count(level)
        print(f"  Score {level}: {count} windows ({count/len(scores)*100:.0f}%)")

    # Notable stretches
    def find_stretches(tl):
        stretches = []
        i = 0
        while i < len(tl):
            is_active = tl[i] > 0
            start_idx = i
            while i < len(tl) and (tl[i] > 0) == is_active:
                i += 1
            stretches.append({
                "start": start_idx, "end": i, "duration": i - start_idx,
                "active": is_active, "max_score": max(tl[start_idx:i]),
            })
        return stretches

    stretches = find_stretches(timeline)
    score_labels = {1: "light", 2: "moderate", 3: "big", 4: "roaring"}

    print(f"\nLONGEST LAUGHTER STRETCHES:")
    for s in sorted([s for s in stretches if s["active"]], key=lambda x: -x["duration"])[:10]:
        print(f"  {s['start']//60}:{s['start']%60:02d} - {s['end']//60}:{s['end']%60:02d}  ({s['duration']}s)  peak: {score_labels.get(s['max_score'], '?')}")

    print(f"\nLONGEST SILENT STRETCHES:")
    for s in sorted([s for s in stretches if not s["active"]], key=lambda x: -x["duration"])[:10]:
        print(f"  {s['start']//60}:{s['start']%60:02d} - {s['end']//60}:{s['end']%60:02d}  ({s['duration']}s)")

    print(f"\nROARING MOMENTS (score 4):")
    for w in windows:
        if w["s"] == 4:
            start_sec = w["w"] * WINDOW_SIZE
            end_sec = start_sec + WINDOW_SIZE
            print(f"  {start_sec//60}:{start_sec%60:02d} - {end_sec//60}:{end_sec%60:02d}")

    return {
        "model": model_name,
        "duration": DURATION,
        "api_response_time": elapsed,
        "num_windows": len(windows),
        "expected_windows": num_windows,
        "active_pct": active / DURATION * 100,
        "windows": windows,
        "timeline": timeline,
    }


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    results = []

    for model in MODELS:
        try:
            r = run_model(client, model)
            results.append(r)
        except Exception as e:
            print(f"\n{model} FAILED: {e}")

        if model != MODELS[-1]:
            print("\nWaiting 30s for rate limit...")
            time.sleep(30)

    out = Path(__file__).parent / "test_results_pro.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
