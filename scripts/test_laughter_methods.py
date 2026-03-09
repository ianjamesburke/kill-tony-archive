"""
Test multiple approaches to Gemini laughter detection.
Goal: find a method that reliably returns correct timestamps without post-processing hacks.

Methods:
  A) Event-based with seconds (what we already tried)
  B) Fixed time-window scoring — ask for a score every N seconds (no timestamp generation needed)
  C) Bucketed approach — break audio into windows, ask which windows have laughter
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
DURATION = 365  # 6 min clip

# Method A: Event-based (baseline — we know this works on short clips)
PROMPT_A = """
Listen to this audio and identify every instance of crowd laughter, applause, cheering, or groaning.
Log the precise start and end time IN TOTAL SECONDS from the start of the audio.

Return ONLY a JSON array:
[
  {{"start_seconds": 125, "end_seconds": 130, "type": "laughter", "intensity": "big"}},
  ...
]

- Timestamps must be in TOTAL SECONDS (e.g. 5 minutes 30 seconds = 330, NOT 5.30 or 530)
- intensity: "light", "moderate", "big", "roaring"
- type: "laughter", "applause", "cheering", "groaning"
- Be exhaustive. Timestamp precision matters.
- The audio is approximately {duration} seconds long.
"""

# Method B: Per-5-second scoring — Gemini doesn't generate timestamps, just fills in a grid
PROMPT_B = """
Listen to this audio and rate the crowd reaction intensity for every 5-second window.

The audio is {duration} seconds long. Return a JSON array with exactly {num_windows} entries,
one for each 5-second window starting from second 0:

[
  {{"window": 0, "score": 0}},
  {{"window": 1, "score": 0}},
  {{"window": 2, "score": 3}},
  ...
]

"window" is the window index (0 = seconds 0-4, 1 = seconds 5-9, 2 = seconds 10-14, etc.)

"score" is the crowd reaction level during that window:
  0 = silence (no crowd reaction)
  1 = light (scattered chuckles, mild reaction)
  2 = moderate (solid laughter, clear audience reaction)
  3 = big laughs (strong laughter, loud audience)
  4 = roaring (house comes down, huge reaction, thunderous applause)

IMPORTANT: Return exactly {num_windows} entries, one per window, in order. Every window must have a score.
"""

# Method C: Per-10-second scoring with type
PROMPT_C = """
Listen to this audio and classify the crowd reaction in every 10-second window.

The audio is {duration} seconds long. Return a JSON array with exactly {num_windows} entries:

[
  {{"window": 0, "score": 0, "type": "none"}},
  {{"window": 1, "score": 2, "type": "laughter"}},
  ...
]

"window" is the window index (0 = seconds 0-9, 1 = seconds 10-19, 2 = seconds 20-29, etc.)

"score" is the crowd reaction level:
  0 = silence, 1 = light, 2 = moderate, 3 = big, 4 = roaring

"type" is the dominant reaction type:
  "none", "laughter", "applause", "cheering", "groaning"

Return exactly {num_windows} entries in order.
"""


def run_test(client, prompt, label):
    print(f"\n{'='*60}")
    print(f"METHOD: {label}")
    print(f"{'='*60}")

    uploaded = client.files.upload(file=AUDIO_PATH)
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
                "http_options": {"timeout": 120000},
            },
        )
        elapsed = time.time() - t0

        raw = (response.text or "").strip()
        data = json.loads(raw)
        print(f"  Response in {elapsed:.1f}s, {len(data)} entries")
        return data, elapsed
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass


def show_timeline(per_second, duration, label):
    """Print a compact visual timeline."""
    chars = {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}
    minutes = (duration + 59) // 60
    print(f"\n  {label} timeline:")
    for m in range(minutes):
        start = m * 60
        end = min(start + 60, duration)
        bar = ""
        for s in range(start, end):
            bar += chars.get(per_second[s] if s < len(per_second) else 0, "?")
        print(f"    {m}:00 |{bar}|")
    print(f"    Legend: · silence  ░ light  ▒ moderate  ▓ big  █ roaring")

    active = sum(1 for s in per_second[:duration] if s > 0)
    print(f"    Active seconds: {active}/{duration} ({active/duration*100:.1f}%)")


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    all_timelines = {}

    # Method A: Event-based
    prompt_a = PROMPT_A.format(duration=DURATION)
    events_a, time_a = run_test(client, prompt_a, "A: Event-based (start/end seconds)")

    intensity_map = {"light": 1, "moderate": 2, "big": 3, "roaring": 4}
    timeline_a = [0] * DURATION
    for e in events_a:
        start = int(e.get("start_seconds", 0))
        end = int(e.get("end_seconds", start))
        score = intensity_map.get(e.get("intensity", "moderate"), 2)
        for s in range(max(0, start), min(DURATION, end)):
            timeline_a[s] = max(timeline_a[s], score)

    show_timeline(timeline_a, DURATION, "A: Event-based")
    all_timelines["A_events"] = timeline_a

    time.sleep(10)

    # Method B: 5-second windows
    num_windows_b = DURATION // 5
    prompt_b = PROMPT_B.format(duration=DURATION, num_windows=num_windows_b)
    windows_b, time_b = run_test(client, prompt_b, "B: 5-second window scoring")

    timeline_b = [0] * DURATION
    for w in windows_b:
        idx = w.get("window", 0)
        score = w.get("score", 0)
        start = idx * 5
        for s in range(start, min(start + 5, DURATION)):
            timeline_b[s] = score

    show_timeline(timeline_b, DURATION, "B: 5-sec windows")
    all_timelines["B_5sec"] = timeline_b

    # Check completeness
    expected = num_windows_b
    got = len(windows_b)
    print(f"  Expected {expected} windows, got {got} {'✓' if got == expected else '✗ MISMATCH'}")

    time.sleep(10)

    # Method C: 10-second windows with type
    num_windows_c = DURATION // 10 + (1 if DURATION % 10 else 0)
    prompt_c = PROMPT_C.format(duration=DURATION, num_windows=num_windows_c)
    windows_c, time_c = run_test(client, prompt_c, "C: 10-second window scoring with type")

    timeline_c = [0] * DURATION
    for w in windows_c:
        idx = w.get("window", 0)
        score = w.get("score", 0)
        start = idx * 10
        for s in range(start, min(start + 10, DURATION)):
            timeline_c[s] = score

    show_timeline(timeline_c, DURATION, "C: 10-sec windows")
    all_timelines["C_10sec"] = timeline_c

    expected = num_windows_c
    got = len(windows_c)
    print(f"  Expected {expected} windows, got {got} {'✓' if got == expected else '✗ MISMATCH'}")

    # Side-by-side comparison
    print(f"\n{'='*60}")
    print(f"COMPARISON (per-minute summary)")
    print(f"{'='*60}")
    print(f"{'Minute':<8} {'A:Events':>10} {'B:5sec':>10} {'C:10sec':>10}")
    print(f"{'-'*8} {'-'*10} {'-'*10} {'-'*10}")

    minutes = (DURATION + 59) // 60
    for m in range(minutes):
        start = m * 60
        end = min(start + 60, DURATION)
        a_active = sum(1 for s in range(start, end) if timeline_a[s] > 0)
        b_active = sum(1 for s in range(start, end) if timeline_b[s] > 0)
        c_active = sum(1 for s in range(start, end) if timeline_c[s] > 0)
        print(f"{m}:00     {a_active:>8}s  {b_active:>8}s  {c_active:>8}s")

    print(f"\n{'Method':<20} {'Events':>8} {'Active%':>8} {'Time':>8}")
    print(f"{'-'*20} {'-'*8} {'-'*8} {'-'*8}")
    for name, tl, t in [("A: Events", timeline_a, time_a),
                          ("B: 5-sec windows", timeline_b, time_b),
                          ("C: 10-sec windows", timeline_c, time_c)]:
        active = sum(1 for s in tl[:DURATION] if s > 0)
        print(f"{name:<20} {len(tl):>8} {active/DURATION*100:>7.1f}% {t:>7.1f}s")

    # Save all results
    results = {
        "duration": DURATION,
        "methods": {
            "A_events": {"raw": events_a, "timeline": timeline_a, "api_time": time_a},
            "B_5sec": {"raw": windows_b, "timeline": timeline_b, "api_time": time_b},
            "C_10sec": {"raw": windows_c, "timeline": timeline_c, "api_time": time_c},
        },
    }
    out = Path(__file__).parent / "test_laughter_methods_results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
