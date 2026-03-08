"""
Hybrid pipeline test: WhisperX (timestamps) → Gemini (speaker labels)

Pass 1:   WhisperX transcribes audio with accurate word-level timestamps
Pass 1.5: Gemini adds speaker labels to the timestamped text (text-only, cheap)

Usage:
    python3 test_whisperx_hybrid.py              # Process chunk 1 of ep 751
    python3 test_whisperx_hybrid.py --chunks 3   # Process first 3 chunks
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

EPISODE = 751
AUDIO_CACHE = Path(__file__).parent / "audio_cache" / f"ep_{EPISODE}"
OUTPUT_DIR = ROOT / "data" / "hybrid_test"

MODELS = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"]

SPEAKER_LABEL_PROMPT = """
You are labeling speakers in a Kill Tony episode transcript. The text has accurate timestamps but NO speaker identification. Your job is to figure out who is speaking for every segment.

This is episode #{episode_number} of Kill Tony, chunk {chunk_num} (starting at {offset_str} into the show).

SPEAKER LABELS (use these EXACT labels):
- "tony" — Tony Hinchcliffe, the host. He introduces comedians, gives feedback, runs the show. Speaks most often outside of sets.
- "redban" — Brian Redban, the co-host. Opens the show ("Hey this is Redban..."), gives number ratings, mentions "secret show", makes side comments. Speaks less than Tony.
- "guest:<full_name>" — Guest judges. Use lowercase with underscores. They give feedback after sets and banter with Tony.
- "comedian:<full_name>" — Performers doing their 1-minute sets. Tony announces each name before their set.
- "crowd" — Audience reactions: laughter, applause, cheering, booing, groaning.
- "band" — Music playing between segments.
- "announcer" — Pre-recorded sponsor reads or show intros.
- "unknown" — Only if truly unidentifiable.

SHOW FORMAT (critical for speaker identification):
1. Redban opens: "Hey this is Redban coming to you live from..."
2. Tony takes over, introduces guest judges by name
3. For each comedian set:
   a. Tony calls their name / pulls from bucket
   b. Comedian performs ~1 minute (60 seconds of uninterrupted speech from one person = the comedian)
   c. Tony gives feedback first, then guests chime in, then back-and-forth interview
4. Between sets: banter between Tony, guests, Redban

KEY IDENTIFICATION RULES:
- After Tony says "60 seconds uninterrupted" or "here we go" or calls a name, the NEXT long stretch of speech is the comedian
- Tony speaks the most — he's the default speaker for host-like statements
- Guests are typically introduced early and give shorter feedback compared to Tony
- Redban rarely speaks long stretches — mostly quick interjections
- If the text contains "[laughter]", "[applause]", "[cheering]", etc., label as "crowd"
- If the text describes music playing, label as "band"

KNOWN REGULARS: Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez, Deadrick Flynn, Ari Matti

OUTPUT: Return a JSON array with ONE entry per input segment, preserving the original segment IDs. For EACH segment:
{{
  "id": <original segment index>,
  "start": <original start seconds>,
  "end": <original end seconds>,
  "speaker": "<speaker label>",
  "text": "<original text>"
}}

IMPORTANT:
- You MUST return exactly {segment_count} entries, one for each input segment
- Preserve the original text EXACTLY — do not modify or summarize it
- If a single segment contains multiple speakers, assign the DOMINANT speaker
- Pay close attention to context — who was just introduced, who is giving feedback, etc.

INPUT SEGMENTS:
{segments}
"""


def run_whisperx(audio_path: str, offset_seconds: int = 0) -> list[dict]:
    """Run WhisperX transcription and return segments with timestamps."""
    import whisperx

    device = "cpu"
    compute_type = "int8"

    print(f"Loading WhisperX model (large-v3)...")
    t0 = time.time()
    model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    print(f"Model loaded in {time.time()-t0:.1f}s")

    print(f"Transcribing {audio_path}...")
    t1 = time.time()
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=4)
    elapsed = time.time() - t1
    print(f"Transcription done in {elapsed:.1f}s ({len(result['segments'])} segments)")

    # Word-level alignment (optional — skip if SSL/download issues)
    try:
        import ssl
        ssl._create_default_https_context()  # Test SSL
        print("Aligning for word-level timestamps...")
        t2 = time.time()
        model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
        result_aligned = whisperx.align(result["segments"], model_a, metadata, audio, device)
        result["segments"] = result_aligned["segments"]
        print(f"Alignment done in {time.time()-t2:.1f}s")
    except Exception as e:
        print(f"Skipping word-level alignment ({type(e).__name__}): segment timestamps still accurate")

    # Add offset to timestamps
    segments = []
    for i, seg in enumerate(result["segments"]):
        segments.append({
            "id": i,
            "start": round(seg["start"] + offset_seconds, 2),
            "end": round(seg["end"] + offset_seconds, 2),
            "text": seg["text"].strip(),
        })

    return segments


def label_speakers(segments: list[dict], episode_number: int, chunk_num: int, offset_seconds: int, model: str | None = None) -> list[dict]:
    """Use Gemini to add speaker labels to WhisperX segments."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    offset_str = f"{offset_seconds // 60}:{offset_seconds % 60:02d}"

    # Format segments for the prompt
    seg_lines = []
    for seg in segments:
        seg_lines.append(f"[{seg['id']}] [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")
    segments_text = "\n".join(seg_lines)

    prompt = SPEAKER_LABEL_PROMPT.format(
        episode_number=episode_number,
        chunk_num=chunk_num,
        offset_str=offset_str,
        segment_count=len(segments),
        segments=segments_text,
    )

    models_to_try = [model] if model else MODELS
    for m in models_to_try:
        try:
            print(f"Labeling speakers with {m} ({len(segments)} segments)...")
            response = client.models.generate_content(
                model=m,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config={"response_mime_type": "application/json"},
            )
            data = json.loads((response.text or "").strip())
            if isinstance(data, dict) and "segments" in data:
                data = data["segments"]
            if not isinstance(data, list):
                raise ValueError(f"Expected list of segments, got {type(data).__name__}")
            print(f"Got {len(data)} labeled segments from {m}")
            return data
        except Exception as e:
            print(f"  {m} failed: {e}")
            if m != models_to_try[-1]:
                print("  Trying next model...")
                time.sleep(5)

    raise RuntimeError("All models failed for speaker labeling")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=int, default=1, help="Number of chunks to process")
    parser.add_argument("--skip-whisperx", action="store_true", help="Skip WhisperX, use cached output")
    parser.add_argument("--model", default=None, help="Specific Gemini model to use")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find audio chunks
    chunk_files = sorted(AUDIO_CACHE.glob("chunk_*.mp3"))
    if not chunk_files:
        print(f"ERROR: No audio chunks in {AUDIO_CACHE}")
        sys.exit(1)

    chunks_to_process = chunk_files[:args.chunks]
    print(f"Processing {len(chunks_to_process)} chunk(s) of episode #{EPISODE}")

    all_labeled = []

    for i, chunk_path in enumerate(chunks_to_process):
        chunk_num = i + 1
        # Parse offset from filename
        import re
        offset_match = re.search(r'_(\d+)s\.mp3$', chunk_path.name)
        offset_seconds = int(offset_match.group(1)) if offset_match else 0

        print(f"\n{'='*60}")
        print(f"CHUNK {chunk_num} — {chunk_path.name} (offset {offset_seconds}s)")
        print(f"{'='*60}")

        # Step 1: WhisperX transcription
        whisperx_cache = OUTPUT_DIR / f"whisperx_chunk{chunk_num}.json"
        if args.skip_whisperx and whisperx_cache.exists():
            print(f"Using cached WhisperX output: {whisperx_cache}")
            with open(whisperx_cache) as f:
                segments = json.load(f)
        else:
            segments = run_whisperx(str(chunk_path), offset_seconds)
            with open(whisperx_cache, "w") as f:
                json.dump(segments, f, indent=2)
            print(f"Saved WhisperX output: {whisperx_cache}")

        # Step 2: Gemini speaker labeling
        labeled = label_speakers(segments, EPISODE, chunk_num, offset_seconds, args.model)

        labeled_path = OUTPUT_DIR / f"labeled_chunk{chunk_num}.json"
        with open(labeled_path, "w") as f:
            json.dump(labeled, f, indent=2)
        print(f"Saved labeled output: {labeled_path}")

        all_labeled.extend(labeled)

    # Save combined output
    combined_path = OUTPUT_DIR / f"ep{EPISODE}_hybrid_transcript.json"
    with open(combined_path, "w") as f:
        json.dump(all_labeled, f, indent=2)
    print(f"\nSaved combined transcript: {combined_path}")

    # Print readable version
    readable_path = OUTPUT_DIR / f"ep{EPISODE}_hybrid_readable.txt"
    with open(readable_path, "w") as f:
        for entry in all_labeled:
            ts = entry.get("start", 0)
            mins = int(ts // 60)
            secs = int(ts % 60)
            speaker = entry.get("speaker", "unknown")
            text = entry.get("text", "")
            line = f"[{mins:02d}:{secs:02d}] {speaker}: {text}"
            f.write(line + "\n")
            print(line)

    print(f"\nReadable transcript: {readable_path}")
    print(f"JSON transcript: {combined_path}")
    print(f"\n>>> Review these files to verify speaker labels are correct <<<")


if __name__ == "__main__":
    main()
