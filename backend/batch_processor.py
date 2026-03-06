"""
Batch processor for Kill Tony episodes.
Two-pass chunked extraction → SQLite storage.

Usage:
    python3 batch_processor.py                  # Process all pending episodes
    python3 batch_processor.py --episode 758    # Process a specific episode
    python3 batch_processor.py --status         # Show processing status
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from yt_dlp import YoutubeDL

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

MODEL = "gemini-3-flash-preview"
CHUNK_MINUTES = 20
OVERLAP_MINUTES = 3
AUDIO_CACHE_DIR = Path(__file__).parent / "audio_cache"
DB_PATH = ROOT / "data" / "kill_tony.db"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
EPISODES_JSON = Path(__file__).parent / "episodes.json"

# Rate limiting — free tier is 15 RPM / 1500 RPD
# We use 10s between API calls (safe margin under 15 RPM)
API_DELAY_SECONDS = 10

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("batch")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

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
      "golden_ticket": false,
      "sign_up_again": false,
      "promoted_to_regular": false,
      "invited_secret_show": false,
      "joke_book_size": "none | small | medium | large",
      "interview_summary": "brief summary of the post-set interview",
      "inferred_gender": "string" | null,
      "inferred_ethnicity": "string" | null,
      "inferred_age": "string" | null
    }}
  ]
}}

FIELD RULES:
- status: ONLY two options: "regular" or "bucket_pull".
  KNOWN REGULARS (always mark as "regular"): Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez.
  IMPORTANT: The regulars list above is NOT exhaustive. New regulars are added over time.
  Also mark status = "regular" if ANY of these signals are present:
    1. Tony introduces them AS a regular (e.g. "our newest regular", "one of our regulars")
    2. Tony says "a brand new set from [name]" — this phrasing is ONLY used for regulars, never bucket pulls
    3. Their set runs significantly longer than 1 minute (regulars typically get 2-3 minutes; bucket pulls get exactly 1 minute)
    4. They are clearly not pulling from the bucket — no name being drawn, no "come on up" moment. For bucket pulls Tony will say things like "let's meet them together" or read the name off a slip of paper.
    5. Tony references them touring together, doing gigs together, or being part of the Kill Tony cast
    6. They close the show (the final set is almost always a regular)
  If NONE of these signals are present and they are not on the known regulars list, status = "bucket_pull".
- Boolean fields default to false. Only set to true when EXPLICITLY stated in the transcript:
  - golden_ticket: Tony awards them a golden ticket
  - sign_up_again: Tony tells them to keep signing up / come back
  - promoted_to_regular: Tony says "you're a regular now" or equivalent
  - invited_secret_show: Redban invites them to his secret show
- tony_praise_level: 1=hated it, 2=not impressed, 3=neutral/okay, 4=liked it, 5=loved it. Base this on Tony's actual words and tone during the interview.
- joke_book_size: Listen for Tony saying "big book", "small book", "no book" — this is a specific Kill Tony bit where Tony judges their joke notebook.
- topic_tags: assign 3-5 tags per set. Choose from: [self_deprecation, politics, relationships, sex, race, crowd_work, observational, shock_humor, storytelling, absurdist, physical, meta, regional, drugs, religion, family, dating, disability, food, aging, lgbtq, crime, work, other]
- set_transcript: copy their EXACT words from the comedian:<name> entries during their set
- set_start_seconds / set_end_seconds: timestamps from the transcript for when their set begins and ends
- inferred_gender: ONLY set if Tony or the comedian explicitly states gender (e.g. "this young lady", "as a woman"). null otherwise.
- inferred_ethnicity: ONLY set if the comedian self-identifies their ethnicity (e.g. "I'm half black", "as a Latina"). null otherwise.
- inferred_age: ONLY set if an age or age range is explicitly mentioned (e.g. "I'm 19", "as a 40-year-old", "this young kid"). Use a string like "19", "40s", "early 20s". null otherwise.

TRANSCRIPT:
{transcript}
"""

# ---------------------------------------------------------------------------
# SQLite Schema (matches SCHEMA.md)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_number INTEGER PRIMARY KEY,
    date TEXT,
    venue TEXT,
    youtube_url TEXT NOT NULL,
    video_id TEXT NOT NULL UNIQUE,
    guests TEXT NOT NULL,            -- JSON array
    laugh_count INTEGER,
    laughter_pct REAL,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    upload_date TEXT,
    processed_at TEXT NOT NULL
    -- full_transcript stored as data/transcripts/ep_{number}.json (gitignored)
);

CREATE TABLE IF NOT EXISTS sets (
    set_id TEXT PRIMARY KEY,         -- {episode_number}_{set_number}
    episode_number INTEGER NOT NULL,
    set_number INTEGER NOT NULL,
    comedian_name TEXT NOT NULL,
    status TEXT NOT NULL,            -- bucket_pull or regular
    set_transcript TEXT,
    set_start_seconds REAL,
    set_end_seconds REAL,
    inferred_gender TEXT,
    inferred_ethnicity TEXT,
    inferred_age TEXT,
    topic_tags TEXT,                 -- JSON array
    joke_count INTEGER,
    crowd_reaction TEXT,
    tony_praise_level INTEGER,
    guest_feedback_sentiment TEXT,
    golden_ticket INTEGER DEFAULT 0,
    sign_up_again INTEGER DEFAULT 0,
    promoted_to_regular INTEGER DEFAULT 0,
    invited_secret_show INTEGER DEFAULT 0,
    joke_book_size TEXT,
    interview_summary TEXT,
    kill_score REAL,
    joke_density REAL,
    FOREIGN KEY (episode_number) REFERENCES episodes(episode_number)
);

CREATE INDEX IF NOT EXISTS idx_sets_episode ON sets(episode_number);
CREATE INDEX IF NOT EXISTS idx_sets_comedian ON sets(comedian_name);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
    log.info(f"Database ready at {DB_PATH}")


# ---------------------------------------------------------------------------
# YouTube metadata + stats
# ---------------------------------------------------------------------------

def get_youtube_info(url: str) -> dict:
    """Extract metadata and stats from YouTube."""
    opts = {"skip_download": True, "quiet": True, "nocheckcertificate": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title", "")
    ep_match = re.search(r'#(\d+)', title) or re.search(r'(?:episode|ep)\s*(\d+)', title, re.IGNORECASE)
    episode_number = int(ep_match.group(1)) if ep_match else None

    return {
        "title": title,
        "episode_number": episode_number,
        "duration": info.get("duration"),
        "video_id": info.get("id"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "upload_date": info.get("upload_date"),
    }


# ---------------------------------------------------------------------------
# Audio download + chunking
# ---------------------------------------------------------------------------

def get_audio_chunks(url: str, episode_number: int) -> tuple[list[Path], list[int]]:
    """Download audio and split into overlapping chunks. Cached per episode."""
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
# Gemini helpers
# ---------------------------------------------------------------------------

def upload_and_wait(client: genai.Client, audio_path: Path):
    uploaded = client.files.upload(file=audio_path)
    for _ in range(120):
        info = client.files.get(name=uploaded.name)
        if info.state == "ACTIVE":
            return uploaded
        time.sleep(1)
    raise RuntimeError(f"File {audio_path.name} never became ACTIVE")


def rate_limit():
    """Sleep to respect API rate limits."""
    time.sleep(API_DELAY_SECONDS)


def _parse_json_array(raw: str) -> list[dict]:
    # Strip markdown code fences
    if "```" in raw:
        raw = re.sub(r"```(?:json)?", "", raw).strip()

    # Try clean parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Normalize whitespace
    raw = re.sub(r"[\r\t]", " ", raw)
    raw = re.sub(r" +", " ", raw).strip()

    # Find array start
    start = raw.find("[")
    if start == -1:
        raise ValueError("No JSON array found")

    # Try to find balanced closing bracket
    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    candidate = raw[start:end] if end > 0 else raw[start:]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Find the last complete entry: ends with }, or } followed by ]
    # Walk backwards from end to find last well-formed closing brace
    # Strategy: find all positions of "}" and try progressively shorter arrays
    for match in reversed(list(re.finditer(r"\}", candidate))):
        pos = match.end()
        truncated = candidate[:pos] + "]"
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            continue

    raise ValueError("Could not recover a valid JSON array from response")


def _deduplicate_entries(entries: list[dict]) -> list[dict]:
    if not entries:
        return entries
    entries.sort(key=lambda x: x.get("start_seconds", 0))
    deduped = [entries[0]]
    for entry in entries[1:]:
        prev = deduped[-1]
        time_close = abs(entry.get("start_seconds", 0) - prev.get("start_seconds", 0)) < 3.0
        text_similar = entry.get("text", "")[:50] == prev.get("text", "")[:50]
        if time_close and text_similar:
            if len(entry.get("text", "")) > len(prev.get("text", "")):
                deduped[-1] = entry
        else:
            deduped.append(entry)
    return deduped


# ---------------------------------------------------------------------------
# Speaker label normalization
# ---------------------------------------------------------------------------

SPEAKER_ALIASES = {
    "uncle_laser": "comedian:uncle_laser",
    "uncle_lazer": "comedian:uncle_laser",
    "comedian:uncle_lazer": "comedian:uncle_laser",
    "hans_kim": "comedian:hans_kim",
    "comedian:hans_kim": "comedian:hans_kim",
    "david_lucas": "comedian:david_lucas",
    "comedian:david_lucas": "comedian:david_lucas",
    "william_montgomery": "comedian:william_montgomery",
    "comedian:william_montgomery": "comedian:william_montgomery",
    "kam_patterson": "comedian:kam_patterson",
    "comedian:kam_patterson": "comedian:kam_patterson",
}


def normalize_speaker(speaker: str) -> str:
    s = speaker.strip().lower().replace(" ", "_")
    return SPEAKER_ALIASES.get(s, s)


# ---------------------------------------------------------------------------
# Two-pass pipeline
# ---------------------------------------------------------------------------

def pass1_transcribe(client: genai.Client, chunk_paths: list[Path], chunk_offsets: list[int]) -> list[dict]:
    log.info(f"PASS 1: Transcribing {len(chunk_paths)} chunks")
    all_entries = []

    for i, chunk_path in enumerate(chunk_paths):
        chunk_num = i + 1
        offset_seconds = chunk_offsets[i]
        offset_str = f"{offset_seconds // 60}:{offset_seconds % 60:02d}"

        log.info(f"  Chunk {chunk_num}/{len(chunk_paths)} (offset {offset_str})")
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
                config={"http_options": {"timeout": 600000}},
            )
            entries = _parse_json_array(response.text.strip())
            log.info(f"    Got {len(entries)} entries")
            all_entries.extend(entries)
        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass

        rate_limit()

    # Normalize speakers
    for entry in all_entries:
        entry["speaker"] = normalize_speaker(entry.get("speaker", "unknown"))

    # Deduplicate
    before = len(all_entries)
    all_entries = _deduplicate_entries(all_entries)
    log.info(f"  Total: {len(all_entries)} entries ({before - len(all_entries)} dupes removed)")

    return all_entries


def pass2_analyze(client: genai.Client, transcript: list[dict], episode_number: int) -> dict:
    log.info("PASS 2: Extracting structured set data")

    lines = []
    for entry in transcript:
        ts = entry.get("start_seconds", 0)
        speaker = entry.get("speaker", "unknown")
        text = entry.get("text", "")
        lines.append(f"[{int(ts//60):02d}:{int(ts%60):02d}] {speaker}: {text}")

    transcript_text = "\n".join(lines)
    prompt = PASS2_PROMPT.format(transcript=transcript_text, episode_number=episode_number)

    response = client.models.generate_content(
        model=MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"response_mime_type": "application/json"},
    )

    data = json.loads(response.text.strip())
    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    rate_limit()
    return data


# ---------------------------------------------------------------------------
# Computed fields
# ---------------------------------------------------------------------------

CROWD_REACTION_SCORES = {
    "silence": 0, "light": 1, "moderate": 2, "big_laughs": 3, "roaring": 4,
}

JOKE_BOOK_SCORES = {
    "none": 0, "small": 1, "medium": 2, "large": 3,
}


def compute_kill_score(s: dict) -> float:
    tony = s.get("tony_praise_level") or 3
    crowd = CROWD_REACTION_SCORES.get(s.get("crowd_reaction", ""), 2)
    book = JOKE_BOOK_SCORES.get(s.get("joke_book_size", ""), 0)
    golden = 10 if s.get("golden_ticket") else 0
    secret = 5 if s.get("invited_secret_show") else 0
    signup = 2 if s.get("sign_up_again") else 0

    return tony * 2 + crowd + book + golden + secret + signup


def compute_laugh_count(transcript: list[dict]) -> int:
    count = 0
    for entry in transcript:
        if entry.get("speaker") == "crowd":
            text = entry.get("text", "").lower()
            if any(w in text for w in ["laughter", "applause", "cheering"]):
                count += 1
    return count


def compute_laughter_pct(transcript: list[dict]) -> float:
    """Percentage of episode duration spent in crowd reactions (laughter/applause/cheering)."""
    if not transcript:
        return 0.0
    crowd_seconds = 0.0
    for entry in transcript:
        if entry.get("speaker") == "crowd":
            start = entry.get("start_seconds", 0)
            end = entry.get("end_seconds", start)
            crowd_seconds += max(0, end - start)
    ep_start = transcript[0].get("start_seconds", 0)
    ep_end = transcript[-1].get("end_seconds", transcript[-1].get("start_seconds", 0))
    ep_duration = ep_end - ep_start
    if ep_duration <= 0:
        return 0.0
    return round((crowd_seconds / ep_duration) * 100, 2)


# ---------------------------------------------------------------------------
# SQLite storage
# ---------------------------------------------------------------------------

def save_episode(yt_info: dict, transcript: list[dict], analysis: dict):
    episode_number = yt_info["episode_number"]
    ep_data = analysis.get("episode", {})
    laugh_count = compute_laugh_count(transcript)
    laughter_pct = compute_laughter_pct(transcript)

    # Save full transcript to flat JSON file (gitignored, for reprocessing only)
    transcript_path = TRANSCRIPTS_DIR / f"ep_{episode_number}.json"
    with open(transcript_path, "w") as f:
        json.dump(transcript, f)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO episodes
            (episode_number, date, venue, youtube_url, video_id, guests,
             laugh_count, laughter_pct, view_count, like_count, comment_count, upload_date, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_number,
            yt_info.get("upload_date"),
            ep_data.get("venue"),
            f"https://www.youtube.com/watch?v={yt_info['video_id']}",
            yt_info["video_id"],
            json.dumps(ep_data.get("guests", [])),
            laugh_count,
            laughter_pct,
            yt_info.get("view_count"),
            yt_info.get("like_count"),
            yt_info.get("comment_count"),
            yt_info.get("upload_date"),
            datetime.now(timezone.utc).isoformat(),
        ))

        # Save sets
        for s in analysis.get("sets", []):
            set_number = s.get("set_number", 0)
            set_id = f"{episode_number}_{set_number}"
            kill_score = compute_kill_score(s)

            # Compute joke density
            joke_density = None
            start = s.get("set_start_seconds")
            end = s.get("set_end_seconds")
            joke_count = s.get("joke_count")
            if start and end and joke_count and (end - start) > 0:
                joke_density = joke_count / (end - start)

            conn.execute("""
                INSERT OR REPLACE INTO sets
                (set_id, episode_number, set_number, comedian_name, status, set_transcript,
                 set_start_seconds, set_end_seconds, inferred_gender, inferred_ethnicity, inferred_age,
                 topic_tags, joke_count, crowd_reaction, tony_praise_level,
                 guest_feedback_sentiment, golden_ticket, sign_up_again, promoted_to_regular,
                 invited_secret_show, joke_book_size, interview_summary, kill_score, joke_density)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                set_id,
                episode_number,
                set_number,
                s.get("comedian_name", "Unknown"),
                s.get("status", "bucket_pull"),
                s.get("set_transcript"),
                start,
                end,
                s.get("inferred_gender"),
                s.get("inferred_ethnicity"),
                s.get("inferred_age"),
                json.dumps(s.get("topic_tags", [])),
                joke_count,
                s.get("crowd_reaction"),
                s.get("tony_praise_level"),
                s.get("guest_feedback_sentiment"),
                1 if s.get("golden_ticket") else 0,
                1 if s.get("sign_up_again") else 0,
                1 if s.get("promoted_to_regular") else 0,
                1 if s.get("invited_secret_show") else 0,
                s.get("joke_book_size"),
                s.get("interview_summary"),
                kill_score,
                joke_density,
            ))

        conn.commit()

    log.info(f"Saved episode #{episode_number}: {len(analysis.get('sets', []))} sets, {laugh_count} laughs")


# ---------------------------------------------------------------------------
# Episode tracking
# ---------------------------------------------------------------------------

def load_episodes() -> list[dict]:
    with open(EPISODES_JSON) as f:
        return json.load(f)["episodes"]


def update_episode_status(episode_number: int, status: str, error: str = None):
    with open(EPISODES_JSON) as f:
        data = json.load(f)

    for ep in data["episodes"]:
        if ep["episode_number"] == episode_number:
            ep["status"] = status
            if error:
                ep["error"] = error
            elif "error" in ep:
                del ep["error"]
            break

    with open(EPISODES_JSON, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_episode(client: genai.Client, ep: dict):
    episode_number = ep["episode_number"]
    url = ep["url"]
    log.info(f"{'='*60}")
    log.info(f"Processing episode #{episode_number}: {ep['title']}")
    log.info(f"{'='*60}")

    update_episode_status(episode_number, "processing")

    # Get YouTube stats
    log.info("Fetching YouTube metadata...")
    yt_info = get_youtube_info(url)
    log.info(f"  Views: {yt_info.get('view_count', 'N/A'):,} | Likes: {yt_info.get('like_count', 'N/A'):,} | Comments: {yt_info.get('comment_count', 'N/A'):,}")

    # Download and chunk audio
    chunk_paths, chunk_offsets = get_audio_chunks(url, episode_number)

    # Pass 1: Transcribe
    transcript = pass1_transcribe(client, chunk_paths, chunk_offsets)

    # Pass 2: Analyze
    analysis = pass2_analyze(client, transcript, episode_number)

    # Save to SQLite
    save_episode(yt_info, transcript, analysis)

    # Summary
    sets = analysis.get("sets", [])
    log.info(f"Episode #{episode_number} complete: {len(sets)} sets extracted")
    for s in sets:
        ks = compute_kill_score(s)
        log.info(f"  #{s.get('set_number')}: {s.get('comedian_name')} ({s.get('status')}) — kill_score={ks:.1f}")

    update_episode_status(episode_number, "done")


def show_status():
    episodes = load_episodes()
    print(f"\n{'Ep#':<6} {'Status':<12} {'Title'}")
    print("-" * 70)
    for ep in episodes:
        status = ep.get("status", "pending")
        marker = {"pending": "  ", "processing": ">>", "done": "OK", "error": "!!"}
        print(f"{marker.get(status, '  ')} {ep['episode_number']:<6} {status:<12} {ep['title'][:50]}")

    done = sum(1 for ep in episodes if ep.get("status") == "done")
    print(f"\n{done}/{len(episodes)} episodes processed")

    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            ep_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]
        print(f"Database: {ep_count} episodes, {set_count} sets")


def main():
    parser = argparse.ArgumentParser(description="Kill Tony batch processor")
    parser.add_argument("--episode", type=int, help="Process a specific episode number")
    parser.add_argument("--status", action="store_true", help="Show processing status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not found in .env")
        sys.exit(1)

    init_db()
    client = genai.Client(api_key=api_key)
    episodes = load_episodes()

    if args.episode:
        ep = next((e for e in episodes if e["episode_number"] == args.episode), None)
        if not ep:
            log.error(f"Episode #{args.episode} not found in episodes.json")
            sys.exit(1)
        try:
            process_episode(client, ep)
        except Exception as e:
            log.error(f"Episode #{args.episode} failed: {e}")
            update_episode_status(args.episode, "error", str(e))
            raise
        return

    # Process all pending episodes
    pending = [e for e in episodes if e.get("status") == "pending"]
    if not pending:
        log.info("No pending episodes to process.")
        show_status()
        return

    total_chunks_est = sum(max(1, e["duration_seconds"] // (CHUNK_MINUTES * 60 - OVERLAP_MINUTES * 60) + 1) for e in pending)
    total_calls_est = total_chunks_est + len(pending)  # chunks + 1 pass2 per episode
    log.info(f"Processing {len(pending)} episodes (~{total_calls_est} API calls, ~{total_calls_est * API_DELAY_SECONDS // 60} min)")

    for i, ep in enumerate(pending):
        log.info(f"\n[{i+1}/{len(pending)}]")
        try:
            process_episode(client, ep)
        except Exception as e:
            log.error(f"Episode #{ep['episode_number']} failed: {e}")
            update_episode_status(ep["episode_number"], "error", str(e))
            continue

    show_status()


if __name__ == "__main__":
    main()
