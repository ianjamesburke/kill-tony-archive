"""
Test: Gemini laughter detection at scale (30 min of ep 738).
Produces per-second laughter scores like YAMNet did with 0.48s frames.
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

AUDIO_PATH = Path(__file__).parent / "test_30min.mp3"
DURATION = 1800  # 30 minutes

PROMPT = """
Listen to this Kill Tony episode audio and identify EVERY instance of crowd laughter, applause, cheering, or groaning.

For each crowd reaction, log the precise start and end time IN SECONDS (not MM:SS).

Return ONLY a JSON array:
[
  {{"start_seconds": 125, "end_seconds": 130, "type": "laughter", "intensity": "big"}},
  ...
]

IMPORTANT:
- Timestamps must be in TOTAL SECONDS from the start of the audio (e.g. 5 minutes 30 seconds = 330, NOT 5.30 or 530)
- intensity levels: "light" (chuckles/scattered), "moderate" (solid laugh), "big" (big laughs), "roaring" (house comes down)
- type: "laughter", "applause", "cheering", "groaning"
- Be exhaustive — catch every reaction, even brief 1-second chuckles
- Timestamp precision matters — try to be accurate to the nearest second
- The audio is approximately 30 minutes (1800 seconds) long
"""


def events_to_per_second(events, duration):
    """Convert laughter events to per-second scores (0.0 to 1.0)."""
    intensity_scores = {
        "light": 0.25,
        "moderate": 0.5,
        "big": 0.75,
        "roaring": 1.0,
    }

    timeline = [0.0] * duration
    for e in events:
        start = int(e.get("start_seconds", 0))
        end = int(e.get("end_seconds", start))
        intensity = e.get("intensity", "moderate")
        score = intensity_scores.get(intensity, 0.5)

        for s in range(max(0, start), min(duration, end)):
            timeline[s] = max(timeline[s], score)

    return timeline


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print(f"Uploading {AUDIO_PATH.name} ({AUDIO_PATH.stat().st_size / 1024 / 1024:.1f} MB)...")
    uploaded = client.files.upload(file=AUDIO_PATH)

    try:
        for _ in range(120):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        print(f"File active. Sending laughter detection prompt...")
        t0 = time.time()

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[PROMPT, uploaded],
            config={
                "response_mime_type": "application/json",
                "http_options": {"timeout": 600000},
            },
        )
        elapsed = time.time() - t0
        print(f"Response received in {elapsed:.1f}s")

        raw = (response.text or "").strip()
        events = json.loads(raw)
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    # Validate timestamps
    bad = [e for e in events if e.get("start_seconds", 0) > DURATION + 10]
    if bad:
        print(f"WARNING: {len(bad)} events have timestamps beyond {DURATION}s (possible MM.SS format leak)")

    # Summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(events)} laughter events in 30 min")
    print(f"{'='*60}")

    total_seconds = 0
    by_type = {}
    by_intensity = {}
    for e in events:
        dur = e.get("end_seconds", 0) - e.get("start_seconds", 0)
        total_seconds += dur
        t = e.get("type", "unknown")
        i = e.get("intensity", "unknown")
        by_type[t] = by_type.get(t, 0) + dur
        by_intensity[i] = by_intensity.get(i, 0) + dur

    print(f"\nTotal crowd reaction time: {total_seconds:.0f}s / {DURATION}s ({total_seconds/DURATION*100:.1f}%)")

    print(f"\nBy type:")
    for t, dur in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t}: {dur:.0f}s ({dur/DURATION*100:.1f}%)")

    print(f"\nBy intensity:")
    for i, dur in sorted(by_intensity.items(), key=lambda x: -x[1]):
        print(f"  {i}: {dur:.0f}s ({dur/DURATION*100:.1f}%)")

    # Per-second timeline
    timeline = events_to_per_second(events, DURATION)
    laugh_seconds = sum(1 for s in timeline if s > 0)
    print(f"\nPer-second breakdown: {laugh_seconds} seconds with laughter ({laugh_seconds/DURATION*100:.1f}%)")

    # Show a compact 5-minute window (minute 1-6, likely first set)
    print(f"\nTimeline sample (0:00 - 5:00, one char per second):")
    for minute in range(5):
        start = minute * 60
        end = start + 60
        bar = ""
        for s in range(start, end):
            v = timeline[s]
            if v == 0:
                bar += "·"
            elif v <= 0.25:
                bar += "░"
            elif v <= 0.5:
                bar += "▒"
            elif v <= 0.75:
                bar += "▓"
            else:
                bar += "█"
        print(f"  {minute}:00 |{bar}| {minute}:59")

    print(f"\n  Legend: · = silence, ░ = light, ▒ = moderate, ▓ = big, █ = roaring")

    # Print all events
    print(f"\nAll events:")
    for e in events:
        s = e["start_seconds"]
        end = e["end_seconds"]
        dur = end - s
        print(f"  {int(s//60)}:{int(s%60):02d} - {int(end//60)}:{int(end%60):02d} ({dur:.0f}s): {e['type']} ({e['intensity']})")

    # Save results
    results = {
        "source": "ep_738_first_30min",
        "duration_seconds": DURATION,
        "api_response_time_seconds": elapsed,
        "total_events": len(events),
        "total_reaction_seconds": total_seconds,
        "laughter_pct": total_seconds / DURATION * 100,
        "events": events,
        "per_second_timeline": timeline,
    }
    out_path = Path(__file__).parent / "test_results_30min.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
