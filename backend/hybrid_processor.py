"""
Hybrid episode processor: WhisperX (local) + Gemini (cloud)

Pass 1:   WhisperX transcription + alignment + speaker diarization (local, free)
Pass 1.5: Gemini maps SPEAKER_XX labels to named speakers (text-only, cheap)
Pass 2:   Gemini extracts structured set data (text-only, cheap)

Usage:
    python3 hybrid_processor.py 754                    # Process episode 754
    python3 hybrid_processor.py 754 --skip-whisperx    # Re-run Gemini passes only
    python3 hybrid_processor.py 754 --dry              # Don't write to DB
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from yt_dlp import YoutubeDL

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# Import shared pieces from batch_processor
sys.path.insert(0, str(Path(__file__).parent))
from batch_processor import (
    PASS2_PROMPT,
    TRANSCRIPTS_DIR,
    compute_kill_score,
    save_episode,
    init_db,
)

AUDIO_CACHE_DIR = Path(__file__).parent / "audio_cache"
CHUNK_MINUTES = 20
OVERLAP_MINUTES = 3
GEMINI_MODELS = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"]
API_DELAY_SECONDS = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hybrid")

# ---------------------------------------------------------------------------
# Speaker mapping prompt (Pass 1.5)
# ---------------------------------------------------------------------------

SPEAKER_MAP_PROMPT = """
You are mapping anonymous speaker labels (SPEAKER_00, SPEAKER_01, etc.) to real names in a Kill Tony episode transcript.

This is episode #{episode_number} of Kill Tony.

Below is the diarized transcript with anonymous speaker labels. Using the text content and show format, identify each speaker.

SPEAKER LABELS to use:
- "tony" — Tony Hinchcliffe, the host
- "redban" — Brian Redban, the co-host
- "guest:<full_name>" — Guest judges (lowercase with underscores)
- "comedian:<full_name>" — Performers (lowercase with underscores)
- "crowd" — Audience reactions
- "band" — Music
- "unknown" — Truly unidentifiable

SHOW FORMAT:
1. Redban opens: "Hey this is Redban coming to you live from..."
2. Tony introduces guest judges by name
3. Each set: Tony calls name → comedian performs ~1 min → interview
4. Between sets: Tony/guests/Redban banter

IDENTIFICATION TIPS:
- The speaker with the MOST segments who introduces others = tony
- The speaker who opens the show with "Redban" in their text = redban
- After Tony says a comedian's name + "here we go", the next speaker doing a long uninterrupted stretch = that comedian
- Tony says "brand new set from [name]" for regulars, pulls names from bucket for bucket pulls
- Guest speakers are introduced early and give feedback after sets

KNOWN REGULARS: Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez, Deadrick Flynn, Ari Matti

Return a JSON object mapping each SPEAKER_XX to their real label:
{{
  "speaker_map": {{
    "SPEAKER_00": "redban",
    "SPEAKER_01": "tony",
    "SPEAKER_02": "comedian:jack_shaw",
    ...
  }},
  "guests": ["Guest Name 1", "Guest Name 2"],
  "venue": "string or null"
}}

TRANSCRIPT (first 300 segments for context):
{transcript_sample}
"""


# ---------------------------------------------------------------------------
# YouTube + Audio
# ---------------------------------------------------------------------------

def get_youtube_info(url: str) -> dict:
    opts = {"skip_download": True, "quiet": True, "nocheckcertificate": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    title = info.get("title", "")
    ep_match = re.search(r'#(\d+)', title) or re.search(r'(?:episode|ep)\s*(\d+)', title, re.IGNORECASE)
    return {
        "title": title,
        "episode_number": int(ep_match.group(1)) if ep_match else None,
        "duration": info.get("duration"),
        "video_id": info.get("id"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "upload_date": info.get("upload_date"),
    }


def get_audio_chunks(url: str, episode_number: int) -> tuple[list[Path], list[int]]:
    cache_dir = AUDIO_CACHE_DIR / f"ep_{episode_number}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(cache_dir.glob("chunk_*.mp3"))
    if existing:
        offsets = []
        for p in existing:
            match = re.search(r'_(\d+)s\.mp3$', p.name)
            offsets.append(int(match.group(1)) if match else 0)
        log.info(f"Using {len(existing)} cached chunks for ep {episode_number}")
        return existing, offsets

    with tempfile.TemporaryDirectory(prefix="kt_") as tmpdir:
        tmp_path = Path(tmpdir)
        outtmpl = str(tmp_path / "audio.%(ext)s")
        opts = {
            "format": "251/bestaudio/best",
            "quiet": True,
            "nocheckcertificate": True,
            "noplaylist": True,
            "outtmpl": outtmpl,
        }
        log.info("Downloading audio...")
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        downloaded = list(tmp_path.glob("audio.*"))
        if not downloaded:
            raise RuntimeError("No audio file downloaded")

        full_mp3 = tmp_path / "full.mp3"
        log.info("Converting to MP3...")
        subprocess.run(
            ["ffmpeg", "-i", str(downloaded[0]), "-q:a", "5", "-y", str(full_mp3)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600,
        )
        downloaded[0].unlink()

        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(full_mp3)],
            capture_output=True, text=True,
        )
        total_duration = float(result.stdout.strip())
        log.info(f"Duration: {total_duration:.0f}s ({total_duration/60:.1f}min)")

        chunk_seconds = CHUNK_MINUTES * 60
        overlap_seconds = OVERLAP_MINUTES * 60
        step_seconds = chunk_seconds - overlap_seconds

        chunk_paths = []
        chunk_offsets = []
        chunk_num = 0
        offset = 0
        while offset < total_duration:
            chunk_num += 1
            chunk_path = cache_dir / f"chunk_{chunk_num:02d}_{offset}s.mp3"
            subprocess.run(
                ["ffmpeg", "-i", str(full_mp3), "-ss", str(offset), "-t", str(chunk_seconds),
                 "-q:a", "5", "-y", str(chunk_path)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
            )
            chunk_paths.append(chunk_path)
            chunk_offsets.append(offset)
            offset += step_seconds

        log.info(f"Split into {len(chunk_paths)} chunks")
        return chunk_paths, chunk_offsets


# ---------------------------------------------------------------------------
# Pass 1: WhisperX
# ---------------------------------------------------------------------------

def pass1_whisperx(chunk_paths: list[Path], chunk_offsets: list[int], cache_dir: Path, use_diarization: bool = True) -> list[dict]:
    import whisperx
    from whisperx.diarize import DiarizationPipeline, assign_word_speakers

    device = "cpu"
    compute_type = "int8"
    HF_TOKEN = os.getenv("HF_TOKEN")

    log.info("Loading WhisperX model (large-v3)...")
    model = whisperx.load_model("large-v3", device, compute_type=compute_type)

    # Load alignment model once
    log.info("Loading alignment model...")
    model_a, metadata = whisperx.load_align_model(language_code="en", device=device)

    # Load diarization model once if needed
    diarize_model = None
    if use_diarization and HF_TOKEN:
        log.info("Loading diarization model...")
        diarize_model = DiarizationPipeline(token=HF_TOKEN, device=device)
    elif use_diarization:
        log.warning("No HF_TOKEN — skipping diarization")

    all_segments = []

    for i, chunk_path in enumerate(chunk_paths):
        chunk_num = i + 1
        offset_seconds = chunk_offsets[i]
        cache_file = cache_dir / f"whisperx_chunk{chunk_num}.json"

        if cache_file.exists():
            log.info(f"Chunk {chunk_num}/{len(chunk_paths)}: using cached WhisperX output")
            with open(cache_file) as f:
                segments = json.load(f)
            all_segments.extend(segments)
            continue

        log.info(f"Chunk {chunk_num}/{len(chunk_paths)}: transcribing {chunk_path.name} (offset {offset_seconds}s)")
        t0 = time.time()

        audio = whisperx.load_audio(str(chunk_path))
        result = model.transcribe(audio, batch_size=4)
        log.info(f"  Transcribed in {time.time()-t0:.0f}s ({len(result['segments'])} segments)")

        # Alignment
        t1 = time.time()
        result = whisperx.align(result["segments"], model_a, metadata, audio, device)
        log.info(f"  Aligned in {time.time()-t1:.0f}s ({len(result['segments'])} segments)")

        # Diarization
        if diarize_model:
            t2 = time.time()
            diarize_result = diarize_model(str(chunk_path))
            result = assign_word_speakers(diarize_result, result)
            log.info(f"  Diarized in {time.time()-t2:.0f}s")

        # Build segments with offset
        segments = []
        for j, seg in enumerate(result["segments"]):
            segments.append({
                "id": len(all_segments) + j,
                "start": round(seg["start"] + offset_seconds, 2),
                "end": round(seg["end"] + offset_seconds, 2),
                "text": seg["text"].strip(),
                "speaker": seg.get("speaker", "unknown"),
            })

        # Cache
        with open(cache_file, "w") as f:
            json.dump(segments, f, indent=2)

        all_segments.extend(segments)

    # Deduplicate overlap regions
    all_segments.sort(key=lambda x: x["start"])
    deduped = [all_segments[0]] if all_segments else []
    for seg in all_segments[1:]:
        prev = deduped[-1]
        if abs(seg["start"] - prev["start"]) < 3.0 and seg["text"][:50] == prev["text"][:50]:
            if len(seg["text"]) > len(prev["text"]):
                deduped[-1] = seg
        else:
            deduped.append(seg)

    # Re-index
    for i, seg in enumerate(deduped):
        seg["id"] = i

    log.info(f"Pass 1 complete: {len(deduped)} segments ({len(all_segments) - len(deduped)} dupes removed)")
    return deduped


# ---------------------------------------------------------------------------
# Pass 1.5: Gemini speaker mapping
# ---------------------------------------------------------------------------

def pass15_map_speakers(client: genai.Client, segments: list[dict], episode_number: int) -> tuple[list[dict], list[str], str | None]:
    log.info("Pass 1.5: Mapping anonymous speakers to names")

    # Build a sample of the transcript for the prompt
    sample_lines = []
    for seg in segments[:300]:
        sample_lines.append(f"[{seg['start']:.1f}s] [{seg['speaker']}] {seg['text']}")
    transcript_sample = "\n".join(sample_lines)

    prompt = SPEAKER_MAP_PROMPT.format(
        episode_number=episode_number,
        transcript_sample=transcript_sample,
    )

    # Try models
    for model in GEMINI_MODELS:
        try:
            log.info(f"  Mapping speakers with {model}...")
            response = client.models.generate_content(
                model=model,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config={"response_mime_type": "application/json"},
            )
            data = json.loads(response.text.strip())
            if isinstance(data, list) and len(data) == 1:
                data = data[0]
            break
        except Exception as e:
            log.warning(f"  {model} failed: {e}")
            if model == GEMINI_MODELS[-1]:
                raise
            time.sleep(API_DELAY_SECONDS)

    speaker_map = data.get("speaker_map", {})
    guests = data.get("guests", [])
    venue = data.get("venue")

    log.info(f"  Speaker map: {json.dumps(speaker_map)}")
    log.info(f"  Guests: {guests}")

    # Apply mapping to all segments
    for seg in segments:
        raw_speaker = seg.get("speaker", "unknown")
        seg["speaker"] = speaker_map.get(raw_speaker, raw_speaker)

    # Convert to Pass 2 format (matching what batch_processor expects)
    transcript = []
    for seg in segments:
        transcript.append({
            "start_seconds": seg["start"],
            "end_seconds": seg["end"],
            "speaker": seg["speaker"],
            "text": seg["text"],
        })

    return transcript, guests, venue


# ---------------------------------------------------------------------------
# Pass 2: Gemini structured extraction
# ---------------------------------------------------------------------------

def pass2_analyze(client: genai.Client, transcript: list[dict], episode_number: int) -> dict:
    log.info("Pass 2: Extracting structured set data")

    lines = []
    for entry in transcript:
        ts = entry.get("start_seconds", 0)
        speaker = entry.get("speaker", "unknown")
        text = entry.get("text", "")
        lines.append(f"[{int(ts//60):02d}:{int(ts%60):02d}] {speaker}: {text}")

    transcript_text = "\n".join(lines)
    prompt = PASS2_PROMPT.format(transcript=transcript_text, episode_number=episode_number)

    for model in GEMINI_MODELS:
        try:
            log.info(f"  Analyzing with {model} ({len(lines)} lines)...")
            response = client.models.generate_content(
                model=model,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config={"response_mime_type": "application/json"},
            )
            data = json.loads(response.text.strip())
            if isinstance(data, list) and len(data) == 1:
                data = data[0]
            return data
        except Exception as e:
            log.warning(f"  {model} failed: {e}")
            if model == GEMINI_MODELS[-1]:
                raise
            time.sleep(API_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Hybrid WhisperX + Gemini episode processor")
    parser.add_argument("episode", type=int, help="Episode number to process")
    parser.add_argument("--skip-whisperx", action="store_true", help="Use cached WhisperX output")
    parser.add_argument("--no-diarize", action="store_true", help="Skip speaker diarization")
    parser.add_argument("--dry", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not found in .env")
        sys.exit(1)

    # Find episode in episodes.json
    episodes_path = Path(__file__).parent / "episodes.json"
    with open(episodes_path) as f:
        episodes = json.load(f)["episodes"]
    ep = next((e for e in episodes if e["episode_number"] == args.episode), None)
    if not ep:
        log.error(f"Episode #{args.episode} not found in episodes.json")
        sys.exit(1)

    episode_number = ep["episode_number"]
    url = ep["url"]
    log.info(f"Processing episode #{episode_number}: {ep['title']}")

    # YouTube metadata
    log.info("Fetching YouTube metadata...")
    yt_info = get_youtube_info(url)
    # Ensure episode_number is set (regex parse from title can fail)
    yt_info["episode_number"] = episode_number

    # Download + chunk audio
    chunk_paths, chunk_offsets = get_audio_chunks(url, episode_number)

    # Cache dir for WhisperX intermediate files
    whisperx_cache_dir = ROOT / "data" / "whisperx_cache" / f"ep_{episode_number}"
    whisperx_cache_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: WhisperX
    if args.skip_whisperx:
        transcript_cache = TRANSCRIPTS_DIR / f"ep_{episode_number}_hybrid.json"
        if transcript_cache.exists():
            log.info(f"Using cached hybrid transcript: {transcript_cache}")
            with open(transcript_cache) as f:
                transcript = json.load(f)
        else:
            log.error("No cached hybrid transcript found. Run without --skip-whisperx first.")
            sys.exit(1)
    else:
        raw_segments = pass1_whisperx(
            chunk_paths, chunk_offsets, whisperx_cache_dir,
            use_diarization=not args.no_diarize,
        )

        # Save raw WhisperX output
        raw_path = whisperx_cache_dir / "full_diarized.json"
        with open(raw_path, "w") as f:
            json.dump(raw_segments, f, indent=2)
        log.info(f"Saved raw WhisperX output: {raw_path}")

        # Pass 1.5: Speaker mapping
        client = genai.Client(api_key=api_key)
        transcript, _guests, _venue = pass15_map_speakers(client, raw_segments, episode_number)

        # Save labeled transcript
        transcript_cache = TRANSCRIPTS_DIR / f"ep_{episode_number}_hybrid.json"
        with open(transcript_cache, "w") as f:
            json.dump(transcript, f, indent=2)
        log.info(f"Saved hybrid transcript: {transcript_cache}")

        # Also save as the standard transcript (for laughter_pct computation etc)
        standard_path = TRANSCRIPTS_DIR / f"ep_{episode_number}.json"
        with open(standard_path, "w") as f:
            json.dump(transcript, f)

        time.sleep(API_DELAY_SECONDS)

    # Pass 2: Structured extraction
    client = genai.Client(api_key=api_key)
    analysis = pass2_analyze(client, transcript, episode_number)

    # Save analysis
    analysis_path = ROOT / "data" / f"hybrid_ep{episode_number}_pass2.json"
    with open(analysis_path, "w") as f:
        json.dump(analysis, f, indent=2)
    log.info(f"Saved analysis: {analysis_path}")

    # Print summary
    sets = analysis.get("sets", [])
    log.info(f"Episode #{episode_number}: {len(sets)} sets extracted")
    for s in sets:
        ks = compute_kill_score(s)
        duration = (s.get("set_end_seconds", 0) - s.get("set_start_seconds", 0))
        log.info(f"  #{s.get('set_number')}: {s.get('comedian_name')} ({s.get('status')}) "
                 f"@ {int(s.get('set_start_seconds',0)//60)}:{int(s.get('set_start_seconds',0)%60):02d} "
                 f"({duration:.0f}s) kill={ks:.0f}")

    if args.dry:
        log.info("[DRY RUN] No changes written to database.")
        return

    # Save to DB
    init_db()
    save_episode(yt_info, transcript, analysis)
    log.info(f"Database updated for episode #{episode_number}")

    # Update episodes.json status
    for e in episodes:
        if e["episode_number"] == episode_number:
            e["status"] = "done"
            break
    with open(episodes_path, "w") as f:
        json.dump({"episodes": episodes}, f, indent=2)


if __name__ == "__main__":
    main()
