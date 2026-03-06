"""
Two-pass extraction test:
  Pass 1: Overlapping audio chunks → dense speaker-labeled transcript
  Pass 2: Text transcript → structured set analysis
"""

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from yt_dlp import YoutubeDL

root_env = Path(__file__).parent.parent / ".env"
if root_env.exists():
    load_dotenv(root_env)

YOUTUBE_URL = "https://www.youtube.com/watch?v=hpncO7ak9m8"
MODEL = "gemini-3-flash-preview"
CHUNK_MINUTES = 20
OVERLAP_MINUTES = 3  # Each chunk overlaps the next by this much

# Cache dir for audio chunks
CACHE_DIR = Path(__file__).parent / "audio_cache"

# --- PASS 1: Transcription only ---
PASS1_PROMPT = """
Transcribe this Kill Tony episode audio segment as accurately and densely as possible.
This is segment {chunk_num} of the episode, starting at {offset_str} into the show.

IMPORTANT: Add {offset_seconds} to all your timestamps since this audio starts at {offset_str} into the full episode.

KNOWN SPEAKERS (use these EXACT labels):
- "tony" — Tony Hinchcliffe, the host. He introduces comedians, gives feedback after sets, and runs the show.
- "redban" — Brian Redban, the co-host. He does the show intro ("Hey this is Redban..."), sometimes gives number ratings, mentions his "secret show", and makes side comments.
- "guest:<full_name>" — Guest judges on the panel. Identify them from how Tony introduces them. Use lowercase with underscores, e.g. "guest:donnell_rawlings", "guest:trevor_wallace".
- "comedian:<full_name>" — Audience members performing 1-minute sets. Tony announces their name before each set. Use lowercase with underscores, e.g. "comedian:uncle_lazer".
- "crowd" — Audience reactions only (laughter, applause, cheering, booing).
- "announcer" — Pre-recorded sponsor reads or show intros.
- "band" — The band playing music.
- "unknown" — Only if you truly cannot identify the speaker.

KNOWN REGULARS (these are recurring performers, NOT bucket pulls):
Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez

SHOW FORMAT (to help you identify who is speaking):
1. Redban opens the show with "Hey this is Redban coming to you live from..."
2. Tony takes over and introduces the guest judges
3. For each set: Tony pulls a name → comedian performs ~1 minute → Tony/guests/Redban give feedback and interview the comedian
4. Between sets there may be banter between Tony, guests, and Redban

OUTPUT FORMAT — Return ONLY a JSON array:
[
  {{"start_seconds": 0.0, "end_seconds": 3.5, "speaker": "redban", "text": "Hey this is Redban..."}},
  {{"start_seconds": 3.5, "end_seconds": 4.0, "speaker": "crowd", "text": "[cheering]"}}
]

RULES:
- Start a NEW entry every time the speaker changes.
- Include ALL speech — do not skip or summarize anything.
- Transcribe comedian sets WORD FOR WORD.
- For crowd/band, use descriptions: [laughter], [applause], [cheering], [groaning], [music], [silence].
- Be precise with timestamps — aim for entries every few seconds.
- Do NOT combine multiple speakers into one entry.
- Remember to offset all timestamps by {offset_seconds} seconds.
"""

# --- PASS 2: Analysis from transcript text ---
PASS2_PROMPT = """
You are analyzing a Kill Tony episode transcript with speaker labels.
This is episode #{episode_number} of Kill Tony.

Extract structured data for every comedian set you find. Return ONLY valid JSON (as a single object, NOT wrapped in an array):

{{
  "episode": {{
    "episode_number": {episode_number},
    "guests": ["name", ...],
    "venue": "string" | null
  }},
  "sets": [
    {{
      "set_number": int,
      "comedian_name": "string",
      "status": "bucket_pull | regular",
      "set_transcript": "their full 1-minute set text, word for word from the transcript",
      "set_start_seconds": float,
      "set_end_seconds": float,
      "topic_tags": ["string"],
      "joke_count": int | null,
      "crowd_reaction": "silence | light | moderate | big_laughs | roaring",
      "tony_praise_level": int (1-5) | null,
      "guest_feedback_sentiment": "positive | negative | neutral | none",
      "walked_off": false,
      "golden_ticket": false,
      "sign_up_again": false,
      "promoted_to_regular": false,
      "invited_secret_show": false,
      "joke_book_size": "none | small | medium | large",
      "interview_summary": "brief summary of the post-set interview"
    }}
  ]
}}

FIELD RULES:
- status: ONLY two options: "regular" or "bucket_pull".
  KNOWN REGULARS: Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez.
  If the comedian is on this list, status = "regular". Everyone else = "bucket_pull" (including first-timers).
- Boolean fields default to false. Only set to true when EXPLICITLY stated in the transcript:
  - walked_off: comedian leaves stage before their minute is up
  - golden_ticket: Tony awards them a golden ticket
  - sign_up_again: Tony tells them to keep signing up / come back
  - promoted_to_regular: Tony says "you're a regular now" or equivalent
  - invited_secret_show: Redban invites them to his secret show
- tony_praise_level: 1=hated it, 2=not impressed, 3=neutral/okay, 4=liked it, 5=loved it. Base this on Tony's actual words and tone during the interview.
- joke_book_size: Listen for Tony saying "big book", "small book", "no book" — this is a specific Kill Tony bit where Tony judges their joke notebook.
- topic_tags: assign 3-5 tags per set. Choose from: [self_deprecation, politics, relationships, sex, race, crowd_work, observational, shock_humor, storytelling, absurdist, physical, meta, regional, drugs, religion, family, dating, disability, food, aging, lgbtq, crime, work, other]
- set_transcript: copy their EXACT words from the comedian:<name> entries during their set
- set_start_seconds / set_end_seconds: timestamps from the transcript for when their set begins and ends

TRANSCRIPT:
{transcript}
"""


def get_episode_metadata(youtube_url: str) -> dict:
    """Extract episode number and title from YouTube metadata."""
    opts = {
        "skip_download": True,
        "quiet": True,
        "nocheckcertificate": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)

    title = info.get("title", "")
    ep_match = re.search(r'#(\d+)', title) or re.search(r'(?:episode|ep)\s*(\d+)', title, re.IGNORECASE)
    episode_number = int(ep_match.group(1)) if ep_match else None

    return {
        "title": title,
        "episode_number": episode_number,
        "duration": info.get("duration"),
    }


def get_audio_and_chunks(youtube_url: str) -> tuple[list[Path], list[int]]:
    """Download audio and split into overlapping chunks.
    Returns (chunk_paths, chunk_offsets_seconds)."""
    CACHE_DIR.mkdir(exist_ok=True)

    # Check if chunks already exist
    existing_chunks = sorted(CACHE_DIR.glob("chunk_*.mp3"))
    if existing_chunks:
        # Reconstruct offsets from filenames
        offsets = []
        for p in existing_chunks:
            # Filename: chunk_01_0s.mp3, chunk_02_1020s.mp3, etc.
            match = re.search(r'_(\d+)s\.mp3$', p.name)
            offsets.append(int(match.group(1)) if match else 0)
        print(f"Using {len(existing_chunks)} cached audio chunks from {CACHE_DIR}")
        return existing_chunks, offsets

    # Download full audio
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

        print("Downloading audio (this may take a while)...")
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(youtube_url, download=True)

        downloaded = list(tmp_path.glob("audio.*"))
        if not downloaded:
            raise RuntimeError("No audio file found")

        original = downloaded[0]

        # Convert to single MP3 first
        full_mp3 = tmp_path / "full.mp3"
        print("Converting to MP3...")
        subprocess.run(
            ["ffmpeg", "-i", str(original), "-q:a", "5", "-y", str(full_mp3)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600,
        )
        original.unlink()

        # Get duration
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(full_mp3)],
            capture_output=True, text=True
        )
        total_duration = float(result.stdout.strip())
        print(f"Total duration: {total_duration:.0f}s ({total_duration/60:.1f}min)")

        # Split into overlapping chunks
        chunk_seconds = CHUNK_MINUTES * 60
        overlap_seconds = OVERLAP_MINUTES * 60
        step_seconds = chunk_seconds - overlap_seconds  # How far to advance each chunk

        chunk_paths = []
        chunk_offsets = []
        chunk_num = 0

        offset = 0
        while offset < total_duration:
            chunk_num += 1
            chunk_path = CACHE_DIR / f"chunk_{chunk_num:02d}_{offset}s.mp3"
            end = min(offset + chunk_seconds, total_duration)
            subprocess.run(
                ["ffmpeg", "-i", str(full_mp3), "-ss", str(offset), "-t", str(chunk_seconds),
                 "-q:a", "5", "-y", str(chunk_path)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
            )
            size_mb = chunk_path.stat().st_size / 1024 / 1024
            print(f"  Chunk {chunk_num}: {offset//60:.0f}min-{end//60:.0f}min ({size_mb:.1f}MB)")
            chunk_paths.append(chunk_path)
            chunk_offsets.append(offset)
            offset += step_seconds

        print(f"Split into {len(chunk_paths)} chunks ({CHUNK_MINUTES}min each, {OVERLAP_MINUTES}min overlap)")
        return chunk_paths, chunk_offsets


def upload_and_wait(client: genai.Client, audio_path: Path):
    """Upload audio to Gemini and wait for ACTIVE state."""
    print(f"  Uploading {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f}MB)...")
    uploaded = client.files.upload(file=audio_path)
    for _ in range(120):
        info = client.files.get(name=uploaded.name)
        if info.state == "ACTIVE":
            return uploaded
        time.sleep(1)
    raise RuntimeError("File never became ACTIVE")


def _parse_json_array(raw: str) -> list[dict]:
    """Parse a JSON array, handling common Gemini quirks."""
    if raw.startswith("```"):
        raw = raw.lstrip("`").lstrip("json").lstrip("\n")
        raw = raw.rstrip("`").rstrip("\n").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    raw = raw.replace("\n", " ").replace("\r", "").replace("\t", " ")
    raw = re.sub(r"\s+", " ", raw).strip()

    start = raw.find("[")
    if start == -1:
        raise ValueError("No JSON array found in response")

    depth = 0
    end = start
    for i in range(start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    raw = raw[start:end]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        last_brace = raw.rfind("}")
        if last_brace > 0:
            truncated = raw[:last_brace + 1] + "]"
            try:
                return json.loads(truncated)
            except json.JSONDecodeError:
                pass
        return json.loads(raw)


def _deduplicate_entries(entries: list[dict]) -> list[dict]:
    """Remove duplicate entries from overlapping chunks.

    Two entries are considered duplicates if their timestamps are within 3 seconds
    and their text is similar (first 50 chars match).
    """
    if not entries:
        return entries

    entries.sort(key=lambda x: x.get("start_seconds", 0))
    deduped = [entries[0]]

    for entry in entries[1:]:
        prev = deduped[-1]
        time_close = abs(entry.get("start_seconds", 0) - prev.get("start_seconds", 0)) < 3.0
        text_similar = entry.get("text", "")[:50] == prev.get("text", "")[:50]

        if time_close and text_similar:
            # Keep the longer text version
            if len(entry.get("text", "")) > len(prev.get("text", "")):
                deduped[-1] = entry
        else:
            deduped.append(entry)

    return deduped


def pass1_transcribe_chunks(client: genai.Client, chunk_paths: list[Path], chunk_offsets: list[int]) -> list[dict]:
    """Pass 1: Transcribe each audio chunk, then merge and deduplicate."""
    print(f"\n=== PASS 1: Transcribing {len(chunk_paths)} overlapping chunks ===")
    all_entries = []

    for i, chunk_path in enumerate(chunk_paths):
        chunk_num = i + 1
        offset_seconds = chunk_offsets[i]
        offset_min = offset_seconds // 60
        offset_str = f"{offset_min}:{offset_seconds % 60:02d}"

        print(f"\n--- Chunk {chunk_num}/{len(chunk_paths)} (starts at {offset_str}) ---")
        uploaded = upload_and_wait(client, chunk_path)

        try:
            prompt = PASS1_PROMPT.format(
                chunk_num=chunk_num,
                offset_seconds=offset_seconds,
                offset_str=offset_str,
            )

            response = client.models.generate_content(
                model=MODEL,
                contents=[prompt, uploaded],
            )

            raw = response.text.strip()
            entries = _parse_json_array(raw)
            print(f"  Got {len(entries)} entries (timestamps {entries[0].get('start_seconds',0):.0f}s - {entries[-1].get('end_seconds', entries[-1].get('start_seconds',0)):.0f}s)")
            all_entries.extend(entries)

        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass

    # Deduplicate overlapping regions
    before_dedup = len(all_entries)
    all_entries = _deduplicate_entries(all_entries)
    print(f"\nTotal entries: {len(all_entries)} ({before_dedup - len(all_entries)} duplicates removed from overlaps)")

    # Speaker breakdown
    speakers = {}
    for entry in all_entries:
        s = entry.get("speaker", "unknown")
        speakers[s] = speakers.get(s, 0) + 1
    print(f"Speaker breakdown: {json.dumps(speakers, indent=2)}")

    return all_entries


def pass2_analyze(client: genai.Client, transcript: list[dict], episode_number: int | None) -> dict:
    """Pass 2: Extract structured set data from transcript text."""
    print("\n=== PASS 2: Analyzing sets from transcript ===")

    lines = []
    for entry in transcript:
        ts = entry.get("start_seconds", 0)
        speaker = entry.get("speaker", "unknown")
        text = entry.get("text", "")
        mins = int(ts // 60)
        secs = int(ts % 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {speaker}: {text}")

    transcript_text = "\n".join(lines)
    ep_num = episode_number if episode_number else "null"
    prompt = PASS2_PROMPT.format(transcript=transcript_text, episode_number=ep_num)

    response = client.models.generate_content(
        model=MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"response_mime_type": "application/json"},
    )

    raw = response.text.strip()
    data = json.loads(raw)

    # Handle Gemini sometimes wrapping in an array
    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    return data


def main():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        return

    # Get episode metadata from YouTube
    print("Fetching episode metadata...")
    metadata = get_episode_metadata(YOUTUBE_URL)
    episode_number = metadata["episode_number"]
    print(f"Title: {metadata['title']}")
    print(f"Episode number: #{episode_number}")
    print(f"Duration: {metadata.get('duration', 0) // 60}min")

    # Download and chunk audio
    chunk_paths, chunk_offsets = get_audio_and_chunks(YOUTUBE_URL)

    client = genai.Client(api_key=api_key)

    # Pass 1: Transcribe all chunks
    transcript = pass1_transcribe_chunks(client, chunk_paths, chunk_offsets)

    # Save pass 1 output
    p1_path = Path(__file__).parent / "test_output_pass1.json"
    with open(p1_path, "w") as f:
        json.dump(transcript, f, indent=2)
    print(f"Saved transcript to {p1_path}")

    # Pass 2: Analyze
    analysis = pass2_analyze(client, transcript, episode_number)

    # Save pass 2 output
    p2_path = Path(__file__).parent / "test_output_pass2.json"
    with open(p2_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"Saved analysis to {p2_path}")

    # Print summary
    print(f"\n{'='*50}")
    print(f"RESULTS")
    print(f"{'='*50}")

    ep = analysis.get("episode", {})
    print(f"Episode: #{ep.get('episode_number', '?')}")
    print(f"Guests: {ep.get('guests', [])}")
    print(f"Venue: {ep.get('venue', '?')}")

    sets = analysis.get("sets", [])
    print(f"\nSets found: {len(sets)}")
    for s in sets:
        ts_start = s.get('set_start_seconds', 0)
        ts_min = int(ts_start // 60)
        ts_sec = int(ts_start % 60)
        print(f"\n  #{s.get('set_number')}: {s.get('comedian_name')} ({s.get('status')}) @ {ts_min}:{ts_sec:02d}")
        print(f"    Topics: {s.get('topic_tags', [])}")
        print(f"    Crowd: {s.get('crowd_reaction')} | Tony praise: {s.get('tony_praise_level')}/5")
        print(f"    Book: {s.get('joke_book_size')} | Jokes: {s.get('joke_count')}")
        print(f"    Golden ticket: {s.get('golden_ticket')} | Sign up again: {s.get('sign_up_again')} | Secret show: {s.get('invited_secret_show')}")
        if s.get('set_transcript'):
            preview = s['set_transcript'][:150]
            print(f"    Set transcript: {preview}...")
        if s.get('interview_summary'):
            print(f"    Interview: {s['interview_summary'][:150]}")


if __name__ == "__main__":
    main()
