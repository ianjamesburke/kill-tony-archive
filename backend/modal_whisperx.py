"""
Modal GPU function for WhisperX transcription (Pass 1).

Runs WhisperX large-v3 on a T4 GPU via Modal's serverless infrastructure.
Returns word-level timestamped segments for Pass 2 processing.

Usage (standalone test):
    python3 -m modal run modal_whisperx.py --episode 742
"""

import json
import time
from pathlib import Path

import modal

app = modal.App("kill-tony-whisperx")

whisperx_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "whisperx",
        "torch",
        "torchaudio",
    )
)


@app.function(
    image=whisperx_image,
    gpu="T4",
    timeout=900,
)
def transcribe(audio_bytes: bytes, model_name: str = "large-v3") -> dict:
    """Transcribe audio with WhisperX on GPU. Returns segments with word-level timestamps."""
    import tempfile
    from pathlib import Path
    import whisperx

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_bytes)
        audio_path = Path(f.name)

    device = "cuda"
    compute_type = "float16"

    print(f"Loading WhisperX model ({model_name}) on {device}...")
    t0 = time.time()
    model = whisperx.load_model(model_name, device, compute_type=compute_type)

    print("Transcribing...")
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=16, language="en")
    transcribe_time = time.time() - t0
    print(f"Transcription done in {transcribe_time:.1f}s ({len(result['segments'])} segments)")

    print("Aligning word timestamps...")
    t1 = time.time()
    model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device)
    align_time = time.time() - t1
    print(f"Alignment done in {align_time:.1f}s")

    total_words = sum(len(s.get("words", [])) for s in result["segments"])
    print(f"Total: {len(result['segments'])} segments, {total_words} words")

    audio_path.unlink(missing_ok=True)

    return {
        "segments": result["segments"],
        "word_segments": result.get("word_segments", []),
        "timings": {
            "transcribe_s": round(transcribe_time, 1),
            "align_s": round(align_time, 1),
            "total_s": round(transcribe_time + align_time, 1),
        },
    }


def format_segments_for_pass2(segments: list[dict]) -> str:
    """Convert WhisperX segments to the timestamped text format Pass 2 expects.

    Output format matches what pass2_analyze() builds from Pass 1:
        [1234s / 20:34] text
    Without speaker labels (Pass 2 prompt handles speaker identification).
    """
    lines = []
    for seg in segments:
        start = seg.get("start", 0)
        ts_sec = int(start)
        text = seg.get("text", "").strip()
        if text:
            lines.append(f"[{ts_sec}s / {ts_sec // 60:02d}:{ts_sec % 60:02d}] {text}")
    return "\n".join(lines)


AUDIO_CACHE = Path(__file__).parent / "audio_cache"
RESULTS_DIR = Path(__file__).parent.parent / "data" / "whisperx_results"


@app.local_entrypoint()
def main(episode: int = 742):
    """Standalone test entrypoint."""
    audio_path = AUDIO_CACHE / f"ep_{episode}" / "full.mp3"
    if not audio_path.exists():
        print(f"No cached audio at {audio_path}")
        return

    RESULTS_DIR.mkdir(exist_ok=True)

    print(f"Reading audio ({audio_path.stat().st_size / 1024 / 1024:.1f} MB)...")
    audio_bytes = audio_path.read_bytes()

    print("Sending to Modal GPU (T4)...")
    t0 = time.time()
    result = transcribe.remote(audio_bytes, model_name="large-v3")
    wall_time = time.time() - t0

    print(f"\nWall time: {wall_time:.1f}s")
    print(f"GPU timings: {result['timings']}")
    print(f"Segments: {len(result['segments'])}")

    result["wall_time_s"] = round(wall_time, 1)
    out = RESULTS_DIR / f"ep_{episode}_whisperx.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"Results saved to {out}")
