"""
Manual laughter labeling tool.

Plays test_clip.mp3 and records keypresses to mark laughter.
Uses raw terminal input — works over SSH, no X/Wayland needed.

Controls:
  ANY KEY  — tap/hold to mark current second as laughter
  q        — quit early

Outputs: scripts/ground_truth_laughter.json
  Per-second array (0 or 1) for the full clip duration.
"""
import argparse
import json
import select
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

AUDIO_PATH = Path(__file__).parent / "test_clip.mp3"
OUTPUT = Path(__file__).parent / "ground_truth_laughter.json"


def get_duration():
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(AUDIO_PATH)],
        capture_output=True, text=True,
    )
    return int(float(result.stdout.strip())) + 1


def main():
    parser = argparse.ArgumentParser(description="Label laughter in test clip")
    parser.add_argument("--mute", action="store_true", help="Don't play audio (dry run for testing)")
    args = parser.parse_args()

    duration = get_duration()
    print(f"Audio: {AUDIO_PATH.name} ({duration}s / {duration//60}m{duration%60}s)")
    if args.mute:
        print(f"MUTED — no audio playback")
    print(f"Tap or hold ANY KEY when you hear crowd laughter.")
    print(f"Press 'q' to quit early.")
    print(f"")
    print(f"Starting in 2 seconds...")
    time.sleep(2)

    timeline = [0] * duration

    # Put terminal in raw mode for keypress detection
    old_settings = termios.tcgetattr(sys.stdin)

    # Play audio in background (unless muted)
    player = None
    if not args.mute:
        player = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(AUDIO_PATH)],
        )

    start_time = time.time()
    last_keypress = 0.0
    key_held = False

    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            elapsed = time.time() - start_time
            sec = int(elapsed)
            if sec >= duration:
                break

            # Check for keypress (non-blocking)
            if select.select([sys.stdin], [], [], 0.04)[0]:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    break
                # Any other key = mark laughter
                last_keypress = elapsed
                key_held = True
                if sec < duration:
                    timeline[sec] = 1
            else:
                # No key pressed this cycle — if last keypress was >0.3s ago, consider released
                if elapsed - last_keypress > 0.3:
                    key_held = False

            # If key is being held (pressed within last 0.3s), keep marking
            if key_held and sec < duration:
                timeline[sec] = 1

            # Progress display (write to stderr to avoid raw mode issues)
            mins = sec // 60
            secs = sec % 60
            bar_width = 50
            progress = sec / duration
            filled = int(bar_width * progress)
            bar = "#" * filled + "-" * (bar_width - filled)
            status = " << LAUGH" if key_held else ""
            sys.stderr.write(f"\r  {mins:02d}:{secs:02d} [{bar}] {sec}/{duration}s{status}    ")
            sys.stderr.flush()

    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        if player:
            player.terminate()

    print(f"\n\nDone!")

    active = sum(timeline)
    print(f"Laughter seconds: {active}/{duration} ({active/duration*100:.1f}%)")

    # Show timeline visualization
    chars = {0: ".", 1: "#"}
    print(f"\nTimeline (each char = 1 second):")
    for m in range(duration // 60 + 1):
        start = m * 60
        end = min(start + 60, duration)
        if start >= duration:
            break
        bar = "".join(chars[timeline[s]] for s in range(start, end))
        print(f"  {m:2d}:00 |{bar}|")

    # Save
    result = {
        "audio_file": AUDIO_PATH.name,
        "duration": duration,
        "window_size": 1,
        "laughter_seconds": active,
        "laughter_pct": round(active / duration * 100, 1),
        "timeline": timeline,
    }
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
