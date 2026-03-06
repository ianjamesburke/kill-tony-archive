"""
Crowd Reaction Detector — YAMNet-based laughter detection.

Runs YAMNet on full episode audio to detect laughter frames, stores
frame-level data for timeline visualization and episode-level totals.

Usage:
    python3 crowd_reaction_detector.py 754          # Process episode 754
    python3 crowd_reaction_detector.py 754 --dry-run  # Analyze only, don't update DB
"""

import argparse
import json
import re
import sqlite3
import subprocess
import time
from pathlib import Path

import numpy as np
import tensorflow_hub as hub
import scipy.io.wavfile as wav

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "kill_tony.db"
AUDIO_CACHE = Path(__file__).parent / "audio_cache"
OUTPUT_DIR = ROOT / "data" / "crowd_reactions"

# YAMNet class indices: 13=Laughter, 14=Baby laughter
LAUGHTER_CLASSES = [13, 14]
CONFIDENCE_THRESHOLD = 0.15
FRAME_DURATION = 0.48  # YAMNet: 960ms window, 480ms hop

_yamnet_model = None


def load_yamnet():
    """Load the YAMNet model from TF Hub (cached after first call)."""
    global _yamnet_model
    if _yamnet_model is not None:
        return _yamnet_model
    print("Loading YAMNet model...")
    t0 = time.time()
    _yamnet_model = hub.load("https://tfhub.dev/google/yamnet/1")
    print(f"YAMNet loaded in {time.time() - t0:.1f}s")
    return _yamnet_model


def audio_chunks_to_wav(episode_number: int) -> str:
    """Concatenate MP3 chunks into a single WAV at 16kHz mono."""
    ep_dir = AUDIO_CACHE / f"ep_{episode_number}"
    if not ep_dir.exists():
        raise FileNotFoundError(f"No audio cache for episode {episode_number}: {ep_dir}")

    chunks = sorted(ep_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise FileNotFoundError(f"No audio chunks in {ep_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = OUTPUT_DIR / f"ep_{episode_number}_full.wav"

    if wav_path.exists():
        print(f"Using cached WAV: {wav_path}")
        return str(wav_path)

    print(f"Converting {len(chunks)} chunks to 16kHz mono WAV...")

    chunk_info = []
    for c in chunks:
        m = re.search(r"_(\d+)s\.mp3$", c.name)
        offset = int(m.group(1)) if m else 0
        chunk_info.append((c, offset))

    n = len(chunk_info)
    inputs = []
    for i, (chunk_path, _offset) in enumerate(chunk_info):
        if i > 0:
            inputs.extend(["-ss", "180", "-i", str(chunk_path)])
        else:
            inputs.extend(["-i", str(chunk_path)])

    filter_complex = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", "16000",
        "-ac", "1",
        str(wav_path),
    ]

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr[-500:]}")
        raise RuntimeError("ffmpeg failed")
    print(f"WAV created in {time.time() - t0:.1f}s: {wav_path}")
    return str(wav_path)


def classify_audio(model, wav_path: str, threshold: float = CONFIDENCE_THRESHOLD) -> tuple[list[dict], float]:
    """Run YAMNet on the full audio. Returns (laughter_frames, total_duration_seconds)."""
    print(f"Reading WAV: {wav_path}")
    sample_rate, audio_data = wav.read(wav_path)

    if audio_data.dtype == np.int16:
        audio_data = audio_data.astype(np.float32) / 32768.0
    elif audio_data.dtype == np.int32:
        audio_data = audio_data.astype(np.float32) / 2147483648.0

    total_duration = len(audio_data) / sample_rate
    print(f"Audio: {total_duration:.0f}s ({total_duration/60:.1f} min) at {sample_rate}Hz")

    print("Running YAMNet classification...")
    t0 = time.time()
    scores, _, _ = model(audio_data)
    scores = scores.numpy()
    elapsed = time.time() - t0
    print(f"Classification done in {elapsed:.1f}s ({scores.shape[0]} frames)")

    frames = []
    for i, frame_scores in enumerate(scores):
        max_score = max(frame_scores[idx] for idx in LAUGHTER_CLASSES)
        if max_score >= threshold:
            frames.append({
                "time": round(i * FRAME_DURATION, 2),
                "score": round(float(max_score), 3),
            })

    print(f"Found {len(frames)} laughter frames out of {scores.shape[0]} total")
    return frames, total_duration


def save_to_db(episode_number: int, frames: list[dict], total_laughter: float,
               dry_run: bool = False):
    """Persist laughter frames and episode total to the database."""
    if dry_run:
        print("[DRY RUN] Would save to DB — skipping")
        return

    conn = sqlite3.connect(DB_PATH)

    # Save laughter frames for timeline visualization
    conn.execute("DELETE FROM laughter_frames WHERE episode_number = ?", (episode_number,))
    conn.executemany(
        "INSERT INTO laughter_frames (episode_number, time_seconds, score) VALUES (?, ?, ?)",
        [(episode_number, f["time"], f["score"]) for f in frames],
    )

    # Update episode-level total
    conn.execute(
        "UPDATE episodes SET total_laughter_seconds = ? WHERE episode_number = ?",
        (total_laughter, episode_number),
    )

    conn.commit()
    conn.close()
    print(f"Saved to DB: {len(frames)} laughter frames, episode total = {total_laughter:.1f}s")


def process_episode(episode_number: int, dry_run: bool = False, threshold: float = CONFIDENCE_THRESHOLD):
    """Full laughter detection pipeline for one episode. Callable from hybrid_processor."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    wav_path = audio_chunks_to_wav(episode_number)
    model = load_yamnet()
    frames, total_duration = classify_audio(model, wav_path, threshold=threshold)

    # Save raw frames JSON
    frames_path = OUTPUT_DIR / f"ep_{episode_number}_frames.json"
    with open(frames_path, "w") as f:
        json.dump(frames, f)

    total_laughter = round(len(frames) * FRAME_DURATION, 1)

    save_to_db(episode_number, frames, total_laughter, dry_run=dry_run)

    print(f"EP {episode_number} — {total_laughter:.1f}s laughter / {total_duration:.0f}s total ({total_laughter/total_duration*100:.1f}%)")

    return {
        "total_laughter_seconds": total_laughter,
        "total_duration": total_duration,
        "frame_count": len(frames),
    }


def main():
    parser = argparse.ArgumentParser(description="Detect laughter in Kill Tony episodes")
    parser.add_argument("episode", type=int, help="Episode number to process")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't update DB")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD,
                        help=f"Confidence threshold (default: {CONFIDENCE_THRESHOLD})")
    args = parser.parse_args()

    process_episode(args.episode, dry_run=args.dry_run, threshold=args.threshold)


if __name__ == "__main__":
    main()
