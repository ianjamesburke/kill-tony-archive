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
import urllib.request
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
GUEST_MODEL = "gemini-3.1-flash-lite-preview"  # cheap model for title parsing
LAUGHTER_MODEL = "gemini-3-flash-preview"  # chunked laughter detection (1500 RPD vs Pro's 50)
LAUGHTER_WINDOW_SIZE = 1  # per-second resolution for event-based detection
PIPELINE_VERSION = 2  # bump when pipeline changes warrant reprocessing (v1=5s windows, v2=events)
CHUNK_MINUTES = 20
OVERLAP_MINUTES = 3
AUDIO_CACHE_DIR = Path(__file__).parent / "audio_cache"
DB_PATH = ROOT / "data" / "kill_tony.db"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
EPISODES_JSON = Path(__file__).parent / "episodes.json"

# Rate limiting — Flash free tier is 15 RPM / 1500 RPD
# We use 10s between API calls (safe margin under 15 RPM)
API_DELAY_SECONDS = 10
# Flash free tier: 15 RPM / 1500 RPD — short backoff on rate limit errors
LAUGHTER_RATE_LIMIT_BACKOFF = 60  # 1 minute between retries on 429

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
    "venue": "string from KNOWN_VENUES list below" | null
  }},
  "sets": [
    {{
      "set_number": int,
      "comedian_name": "string",
      "status": "bucket_pull | regular | special_request",
      "set_transcript": "their full 1-minute set text, word for word from the transcript",
      "set_start_seconds": float,
      "set_end_seconds": float,
      "topic_tags": ["string"],
      "crowd_reaction": "silence | light | moderate | big_laughs | roaring",
      "tony_praise_level": int (1-5) | null,
      "golden_ticket": false,
      "sign_up_again": false,
      "promoted_to_regular": false,
      "invited_secret_show": false,
      "joke_book_size": "none | small | medium | large",
      "interview_summary": "brief summary of the post-set interview",
      "disclosed_age": int | null,
      "disclosed_occupation": "string" | null,
      "disclosed_location": "string" | null,
      "disclosed_relationship_status": "string" | null,
      "disclosed_years_doing_comedy": int | null,
      "fun_facts": ["string"]
    }}
  ]
}}

FIELD RULES:
- venue: Use ONLY one of these known venue names (pick the closest match):
  "Comedy Mothership" (the home venue in Austin — also called "The Mothership", "Mothership"),
  "Moody Center" (arena shows in Austin),
  "Vulcan Gas Company" (previous Austin venue, eps ~300-500s),
  "Antone's Nightclub" (brief Austin venue before Vulcan),
  "The Comedy Store" (original LA venue, early episodes).
  For tour episodes at other venues, use the actual venue name as stated.
  If the venue cannot be determined, use null.
- status: THREE options: "regular", "bucket_pull", or "special_request".
  KNOWN REGULARS (always mark as "regular"): Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez.
  IMPORTANT: The regulars list above is NOT exhaustive. New regulars are added over time.
  Also mark status = "regular" if ANY of these signals are present:
    1. Tony introduces them AS a regular (e.g. "our newest regular", "one of our regulars")
    2. Tony/Redban says "a brand new set from [name]" OR "a brand new minute from [name]" — this phrasing is ONLY used for regulars, never bucket pulls
    3. Their set runs significantly longer than 1 minute (regulars typically get 2-3 minutes; bucket pulls get exactly 1 minute)
    4. They are clearly not pulling from the bucket — no name being drawn, no "come on up" moment. For bucket pulls Tony will say things like "let's meet them together" or read the name off a slip of paper.
    5. Tony references them touring together, doing gigs together, or being part of the Kill Tony cast
    6. They close the show (the final set is almost always a regular)
    7. They are introduced as a "golden ticket winner" who is "visiting", "popping in", or "stopping by" — past GT winners return as regulars; this means status="regular" and golden_ticket=FALSE (they are not winning a new ticket)
  Mark status = "special_request" when someone is brought up OUTSIDE the normal bucket draw or regular rotation:
    - Tony calls them up as a favor, special treat, or because someone on the show (a guest, regular, or bucket pull) mentioned them
    - A bucket pull says they came with a friend/relative and Tony brings that person up too
    - A regular's friend/girlfriend/family member gets called up by Tony
    - A celebrity's friend or associate is invited up (e.g. "Woody Harrelson's stand-in")
    - Tony says something like "special treat", "we have a special guest", "come on up" without a bucket draw
    - Key signal: they did NOT pull their name from the bucket AND they are NOT a recognized regular
  If NONE of these signals are present and they are not on the known regulars list, status = "bucket_pull".
- Boolean fields default to false. Only set to true when EXPLICITLY stated in the transcript:
  - golden_ticket: Tony awards them a golden ticket IN THIS SET. IMPORTANT: if they are merely introduced AS a past golden ticket winner ("one of our golden ticket winners", "our GT winner"), do NOT set this to true — that means they already won it previously and are returning as a regular.
  - sign_up_again: Tony tells them to keep signing up / come back
  - promoted_to_regular: Tony says "you're a regular now" or equivalent
  - invited_secret_show: Redban invites them to his secret show
- tony_praise_level: Rate 1-5 based ONLY on Tony's explicit reaction to the SET PERFORMANCE, not general interview warmth:
  1 = Openly negative — "that was bad/rough/not good", "I don't understand that joke", "that's not how comedy works", dismisses them
  2 = Unimpressed/disappointed — "eh", short dismissive answer, "you have some work to do", no laughs, no specific praise
  3 = Neutral/polite — generic host comments ("nice to meet you", "where you from"), asks interview questions without complimenting the set, or gives mild encouragement with no specific praise ("keep working at it", "you'll get better")
  4 = Genuinely positive — laughs at specific jokes, "I liked that", "that was funny", "good set", calls out a particular joke that worked, real enthusiasm
  5 = High praise — "you killed it", "that was one of the best sets tonight", golden ticket, "you're ready for a special", calls out multiple killer moments, audience still cheering
  DEFAULT TO 3 if Tony doesn't specifically comment on the quality of the set. Most sets are 2-4. Reserve 5 for truly exceptional sets where Tony is visibly impressed.
- joke_book_size: Listen for Tony saying "big book", "small book", "no book" — this is a specific Kill Tony bit where Tony judges their joke notebook.
- topic_tags: assign 3-5 tags per set. Choose from: [self_deprecation, politics, relationships, sex, race, crowd_work, observational, shock_humor, storytelling, absurdist, physical, meta, regional, drugs, religion, family, dating, disability, food, aging, lgbtq, crime, work, other]
- set_transcript: copy their EXACT words from the comedian:<name> entries during their set (only the performance, not the interview)
- set_start_seconds: the timestamp IN SECONDS (the number before "s" in the transcript timestamps, e.g. [2237s / 37:17] means 2237) when the comedian STARTS PERFORMING their material (their first joke/line on the mic). This is NOT when Tony announces their name or when the band plays — it's when the comedian actually begins speaking their set. Look for the first comedian:<name> entry AFTER the band walk-up music.
- set_end_seconds: the timestamp IN SECONDS when the comedian STOPS performing. This is usually when the buzzer sounds, the band starts playing them off, or they say "that's my time" / trail off. It is NOT the end of the interview.
- disclosed_age: integer age ONLY if explicitly stated (e.g. "I'm 23", Tony says "you're 19"). null otherwise.
- disclosed_occupation: their day job or profession if mentioned (e.g. "I'm a nurse", "I work at Costco", "Woody Harrelson's stand-in"). null if not mentioned. This is NOT "comedian" — it's what they do outside comedy.
- disclosed_location: where they live or are from if stated (e.g. "Austin", "I'm from Detroit", "I moved here from New York"). null if not mentioned.
- disclosed_relationship_status: if mentioned (e.g. "single", "married", "divorced", "girlfriend"). null if not mentioned.
- disclosed_years_doing_comedy: integer years if stated (e.g. "I've been doing this 3 years" → 3). null if not mentioned.
- fun_facts: 0-3 memorable or entertaining details from the set/interview that stand out. Things like "is Woody Harrelson's stand-in", "brought their mom to the show", "got fired from their job last week". Only include genuinely interesting tidbits. Empty array [] if nothing stands out.
TRANSCRIPT:
{transcript}
"""

LAUGHTER_PROMPT = """
Listen to this audio clip from a Kill Tony comedy show. Identify every instance of crowd laughter, applause, cheering, or groaning.

Log the precise start and end time IN TOTAL SECONDS from the start of this audio clip.
The audio is approximately {duration} seconds long ({duration_min} minutes).

Return ONLY a JSON array:
[
  {{"start_seconds": 45, "end_seconds": 49, "type": "laughter", "intensity": "big"}},
  {{"start_seconds": 72, "end_seconds": 74, "type": "applause", "intensity": "moderate"}},
  ...
]

Fields:
- start_seconds / end_seconds: integers, in TOTAL SECONDS from the start of THIS audio clip
- type: "laughter", "applause", "cheering", or "groaning"
- intensity: "light", "moderate", "big", or "roaring"

CRITICAL RULES:
- Only log DISTINCT crowd reactions. Background noise, murmuring, and ambient crowd sounds are NOT reactions.
- Most of the show is people talking — there should be long gaps between events.
- A typical 1-minute comedy set has maybe 3-6 laugh moments, not continuous laughter.
- Timestamp precision matters. Be as accurate as possible with start/end times.
- When in doubt about intensity, score LOWER not higher.
- Be exhaustive — catch every reaction, but do NOT invent reactions that aren't there.
"""

# ---------------------------------------------------------------------------
# SQLite Schema (matches SCHEMA.md)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_number INTEGER PRIMARY KEY,
    title TEXT,
    date TEXT,
    venue TEXT,
    youtube_url TEXT NOT NULL,
    video_id TEXT NOT NULL UNIQUE,
    guests TEXT NOT NULL DEFAULT '[]', -- JSON array
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, processing, done, error
    pipeline_version INTEGER DEFAULT 0,     -- bumped when pipeline changes
    laugh_count INTEGER,
    laughter_pct REAL,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    upload_date TEXT,
    processed_at TEXT
    -- full_transcript stored as data/transcripts/ep_{number}.json (gitignored)
);

CREATE TABLE IF NOT EXISTS sets (
    set_id TEXT PRIMARY KEY,         -- {episode_number}_{set_number}
    episode_number INTEGER NOT NULL,
    set_number INTEGER NOT NULL,
    comedian_name TEXT NOT NULL,
    status TEXT NOT NULL,            -- bucket_pull, regular, or special_request
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
    disclosed_age INTEGER,
    disclosed_occupation TEXT,
    disclosed_location TEXT,
    disclosed_relationship_status TEXT,
    disclosed_years_doing_comedy INTEGER,
    disclosed_has_kids INTEGER,
    self_disclosed_extra TEXT,           -- JSON object
    fun_facts TEXT,                      -- JSON array
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

        # Migrate: add new columns if they don't exist yet
        sets_cols = {row[1] for row in conn.execute("PRAGMA table_info(sets)").fetchall()}
        sets_migrations = [
            ("disclosed_age", "INTEGER"),
            ("disclosed_occupation", "TEXT"),
            ("disclosed_location", "TEXT"),
            ("disclosed_relationship_status", "TEXT"),
            ("disclosed_years_doing_comedy", "INTEGER"),
            ("disclosed_has_kids", "INTEGER"),
            ("self_disclosed_extra", "TEXT"),
        ]
        for col, dtype in sets_migrations:
            if col not in sets_cols:
                conn.execute(f"ALTER TABLE sets ADD COLUMN {col} {dtype}")

        ep_cols = {row[1] for row in conn.execute("PRAGMA table_info(episodes)").fetchall()}
        ep_migrations = [
            ("title", "TEXT"),
            ("status", "TEXT DEFAULT 'done'"),
            ("pipeline_version", "INTEGER DEFAULT 0"),
        ]
        for col, dtype in ep_migrations:
            col_name = col.split()[0]
            if col_name not in ep_cols:
                conn.execute(f"ALTER TABLE episodes ADD COLUMN {col} {dtype}")

        # Seed episodes from episodes.json into DB as pending (skip existing)
        if EPISODES_JSON.exists():
            with open(EPISODES_JSON) as f:
                all_episodes = json.load(f).get("episodes", [])
            existing_eps = {row[0] for row in conn.execute("SELECT episode_number FROM episodes").fetchall()}
            seeded = 0
            for ep in all_episodes:
                ep_num = ep.get("episode_number")
                if ep_num and ep_num not in existing_eps:
                    conn.execute(
                        "INSERT INTO episodes (episode_number, title, youtube_url, video_id, guests, status, pipeline_version, processed_at) VALUES (?, ?, ?, ?, '[]', 'pending', 0, '')",
                        (ep_num, ep.get("title", ""), ep.get("url", ""), ep.get("video_id", "")),
                    )
                    seeded += 1
            if seeded:
                conn.commit()
                log.info(f"Seeded {seeded} episodes from episodes.json")

    log.info(f"Database ready at {DB_PATH}")


# ---------------------------------------------------------------------------
# YouTube metadata + stats
# ---------------------------------------------------------------------------

def _yt_cookie_opts() -> dict:
    """Return yt-dlp cookie options if a cookies file or browser is available."""
    cookie_file = ROOT / "cookies.txt"
    if cookie_file.exists():
        return {"cookiefile": str(cookie_file)}
    # Try chromium cookies (works on Linux with keyring access)
    return {"cookiesfrombrowser": ("chromium",)}


def get_youtube_info(url: str) -> dict:
    """Extract metadata and stats from YouTube."""
    opts = {"skip_download": True, "quiet": True, "nocheckcertificate": True, **_yt_cookie_opts()}
    with YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
        info = ydl.extract_info(url, download=False)

    if not info:
        return {"title": "", "episode_number": None, "duration": None,
                "video_id": None, "view_count": None, "like_count": None,
                "comment_count": None, "upload_date": None}

    title = str(info.get("title", "") or "")
    episode_number = extract_episode_number(title)

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
# Guest extraction from YouTube title (NOT from transcript)
# ---------------------------------------------------------------------------

GUEST_EXTRACT_PROMPT = """Extract the guest names from this Kill Tony episode title.
Return ONLY a JSON array of properly capitalized guest names.

Rules:
- Kill Tony is hosted by Tony Hinchcliffe with co-host Brian Redban — NEVER include them as guests.
- If someone is playing a character, use format "Real Name (as Character)" e.g. "Adam Ray (as Dr. Phil)".
- Fix any ALL-CAPS to proper title case.
- If there are no guests, return an empty array [].

Title: {title}"""


def extract_episode_number(title: str) -> int | None:
    """Extract episode number from title. Handles 'KT #758', 'Kill Tony #167', etc."""
    m = re.search(r'#(\d+)', title) or re.search(r'(?:episode|ep)\s*(\d+)', title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def is_valid_episode(title: str, duration_seconds: int | None) -> bool:
    """Check if a video is a real Kill Tony episode (has ep #, is 1+ hour)."""
    if extract_episode_number(title) is None:
        return False
    if duration_seconds is not None and duration_seconds < 3600:
        return False
    return True


def extract_guests_from_title_regex(title: str) -> list[str]:
    """Pure regex guest extraction from YouTube title — no API call needed.
    Handles: 'KT #758 - NAME + NAME', 'Kill Tony #167 - NAME & NAME', etc.
    """
    # Match everything after '#NNN - ' or '#NNN — ' etc.
    match = re.search(r'#\d+\s*[-–—]\s*(.+)', title)
    if match:
        raw = match.group(1)
        # Split on +, &, comma (the three delimiters used across eras)
        names = re.split(r'\s*[+,&]\s*', raw)
        return [n.strip().title() for n in names if n.strip()]
    return []


def extract_guests_from_title(client: genai.Client, title: str) -> list[str]:
    """Extract guest names: try regex first, fall back to Gemini for weird titles."""
    # Try regex first — cheap, handles 95% of titles
    guests = extract_guests_from_title_regex(title)
    if guests:
        log.info(f"  Guests from title (regex): {guests}")
        return guests

    # Gemini fallback for unusual title formats
    log.info("  Regex found no guests, trying Gemini...")
    prompt = GUEST_EXTRACT_PROMPT.format(title=title)
    try:
        resp = client.models.generate_content(
            model=GUEST_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        raw_text = resp.text
        if raw_text is None:
            raise ValueError("Empty response from Gemini")
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            guests = [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
            log.info(f"  Guests from title (Gemini): {guests}")
            return guests
    except Exception as e:
        log.warning(f"  Guest extraction failed (both regex + Gemini): {e}")

    return []


# ---------------------------------------------------------------------------
# Audio download + chunking
# ---------------------------------------------------------------------------

def download_audio(url: str, episode_number: int) -> Path:
    """Download episode audio as a single MP3 file. Cached per episode."""
    cache_dir = AUDIO_CACHE_DIR / f"ep_{episode_number}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    full_path = cache_dir / "full.mp3"
    if full_path.exists():
        log.info(f"Using cached full audio for ep {episode_number}")
        return full_path

    # Check for legacy chunks — if they exist, we still have audio cached
    existing_chunks = sorted(cache_dir.glob("chunk_*.mp3"))
    if existing_chunks:
        log.info(f"Found {len(existing_chunks)} legacy chunks for ep {episode_number} (will use chunked path)")

    with tempfile.TemporaryDirectory(prefix="kt_") as tmpdir:
        tmp_path = Path(tmpdir)
        outtmpl = str(tmp_path / "audio.%(ext)s")
        opts = {
            "format": "251/bestaudio/best",
            "quiet": True,
            "nocheckcertificate": True,
            "noplaylist": True,
            "outtmpl": outtmpl,
            **_yt_cookie_opts(),
        }

        log.info("Downloading audio...")
        with YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
            ydl.extract_info(url, download=True)

        downloaded = list(tmp_path.glob("audio.*"))
        if not downloaded:
            raise RuntimeError("No audio file downloaded")

        log.info("Converting to MP3...")
        subprocess.run(
            ["ffmpeg", "-i", str(downloaded[0]), "-q:a", "5", "-y", str(full_path)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600,
        )

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(full_path)],
        capture_output=True, text=True,
    )
    total_duration = float(result.stdout.strip())
    log.info(f"Duration: {total_duration:.0f}s ({total_duration/60:.1f}min)")

    return full_path


def split_into_chunks(full_mp3: Path, episode_number: int) -> tuple[list[Path], list[int]]:
    """Split a full MP3 into overlapping chunks. Fallback for when full-file transcription fails."""
    cache_dir = full_mp3.parent

    # Check for existing chunks
    existing = sorted(cache_dir.glob("chunk_*.mp3"))
    if existing:
        offsets = []
        for p in existing:
            match = re.search(r'_(\d+)s\.mp3$', p.name)
            offsets.append(int(match.group(1)) if match else 0)
        log.info(f"Using {len(existing)} cached chunks for ep {episode_number}")
        return existing, offsets

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(full_mp3)],
        capture_output=True, text=True,
    )
    total_duration = float(result.stdout.strip())

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
        info = client.files.get(name=uploaded.name or "")
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


def _text_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two strings (0.0 to 1.0)."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 1.0 if words_a == words_b else 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))


def _deduplicate_entries(entries: list[dict]) -> list[dict]:
    if not entries:
        return entries
    entries.sort(key=lambda x: x.get("start_seconds", 0))
    deduped = [entries[0]]
    for entry in entries[1:]:
        is_dupe = False
        # Check against recent entries (overlap can shift timestamps by minutes)
        for prev in deduped[-10:]:
            time_close = abs(entry.get("start_seconds", 0) - prev.get("start_seconds", 0)) < 5.0
            text_sim = _text_similarity(entry.get("text", ""), prev.get("text", ""))
            if time_close and text_sim > 0.6:
                # Keep the longer version
                if len(entry.get("text", "")) > len(prev.get("text", "")):
                    idx = deduped.index(prev)
                    deduped[idx] = entry
                is_dupe = True
                break
        if not is_dupe:
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
    """Transcribe episode audio using overlapping chunks."""
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
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=MODEL,
                        contents=[prompt, uploaded],
                        config={"http_options": {"timeout": 600000}},
                    )
                    break
                except Exception as api_err:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        log.warning(f"    Chunk {chunk_num} attempt {attempt+1} failed ({api_err}), retrying in {wait}s")
                        time.sleep(wait)
                    else:
                        raise
            entries = _parse_json_array((response.text or "").strip())
            log.info(f"    Got {len(entries)} entries")
            all_entries.extend(entries)
        finally:
            try:
                client.files.delete(name=uploaded.name or "")
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
        lines.append(f"[{int(ts)}s / {int(ts//60):02d}:{int(ts%60):02d}] {speaker}: {text}")

    transcript_text = "\n".join(lines)
    prompt = PASS2_PROMPT.format(transcript=transcript_text, episode_number=episode_number)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config={"response_mime_type": "application/json", "http_options": {"timeout": 600000}},
            )
            break
        except Exception as api_err:
            if attempt < 2:
                wait = 30 * (attempt + 1)
                log.warning(f"  Pass 2 attempt {attempt+1} failed ({api_err}), retrying in {wait}s")
                time.sleep(wait)
            else:
                raise

    raw_text = (response.text or "").strip()
    data = json.loads(raw_text)
    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    rate_limit()
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict from Pass 2, got {type(data).__name__}")
    return data


LAUGHTER_CHUNK_SECONDS = 900  # 15 minutes per laughter chunk


INTENSITY_MAP = {"light": 1, "moderate": 2, "big": 3, "roaring": 4}


def _detect_laughter_chunk(client: genai.Client, audio_path: Path, chunk_duration: int, time_offset: int) -> list[dict]:
    """Run event-based laughter detection on a single audio chunk.

    Returns per-second window dicts {"w": global_second, "s": score} for compatibility
    with save_laughter_frames.
    """
    prompt = LAUGHTER_PROMPT.format(
        duration=chunk_duration,
        duration_min=chunk_duration // 60,
    )

    uploaded = upload_and_wait(client, audio_path)
    try:
        for attempt in range(6):
            try:
                response = client.models.generate_content(
                    model=LAUGHTER_MODEL,
                    contents=[prompt, uploaded],
                    config={
                        "response_mime_type": "application/json",
                        "http_options": {"timeout": 600000},
                    },
                )
                break
            except Exception as api_err:
                err_str = str(api_err).lower()
                if "429" in err_str or "rate" in err_str or "quota" in err_str or "resource" in err_str:
                    wait = LAUGHTER_RATE_LIMIT_BACKOFF * (attempt + 1)
                    log.warning(f"  Laughter rate limited (attempt {attempt+1}/6), waiting {wait//60}min...")
                    time.sleep(wait)
                elif attempt < 2:
                    wait = 60 * (attempt + 1)
                    log.warning(f"  Laughter attempt {attempt+1} failed ({api_err}), retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise

        raw = (response.text or "").strip()
        events = json.loads(raw)
        log.info(f"    Got {len(events)} laughter events from chunk")
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    # Convert events to per-second windows with global time offset
    per_second = {}
    for e in events:
        start = int(e.get("start_seconds", 0))
        end = int(e.get("end_seconds", start + 1))
        score = INTENSITY_MAP.get(e.get("intensity", "moderate"), 2)
        for sec in range(max(0, start), min(chunk_duration, end)):
            global_sec = sec + time_offset
            per_second[global_sec] = max(per_second.get(global_sec, 0), score)

    return [{"w": sec, "s": score} for sec, score in sorted(per_second.items())]


def detect_laughter(client: genai.Client, audio_path: Path, episode_number: int) -> list[dict]:
    """Detect crowd laughter using Gemini Flash with event-based timestamps.

    Splits audio into 15-min chunks to minimize timestamp drift.
    Returns list of {"w": second, "s": score} dicts with global timestamps.
    """
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True,
    )
    total_duration = int(float(result.stdout.strip()))

    log.info(f"LAUGHTER DETECTION: {total_duration}s audio, event-based with {LAUGHTER_CHUNK_SECONDS//60}min chunks (using {LAUGHTER_MODEL})")

    # Short enough to process in one shot (under 20 min)
    if total_duration <= 1200:
        return _detect_laughter_chunk(client, audio_path, total_duration, time_offset=0), total_duration

    # Chunk the audio
    all_windows = []
    offset = 0
    chunk_num = 0

    while offset < total_duration:
        chunk_num += 1
        chunk_duration = min(LAUGHTER_CHUNK_SECONDS, total_duration - offset)

        # Extract chunk audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, prefix=f"laugh_chunk_{chunk_num}_") as tmp:
            chunk_path = Path(tmp.name)

        try:
            subprocess.run(
                ["ffmpeg", "-i", str(audio_path), "-ss", str(offset), "-t", str(chunk_duration),
                 "-q:a", "5", "-y", str(chunk_path)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
            )
            log.info(f"  Laughter chunk {chunk_num} ({offset//60}:{offset%60:02d} - {(offset+chunk_duration)//60}:{(offset+chunk_duration)%60:02d})")

            chunk_windows = _detect_laughter_chunk(client, chunk_path, chunk_duration, time_offset=offset)
            all_windows.extend(chunk_windows)
        finally:
            chunk_path.unlink(missing_ok=True)

        offset += LAUGHTER_CHUNK_SECONDS
        rate_limit()

    log.info(f"  Total: {len(all_windows)} laughter seconds detected across {chunk_num} chunks")
    return all_windows, total_duration


def save_laughter_frames(episode_number: int, windows: list[dict], total_duration: int = 0):
    """Store laughter detection results in laughter_frames table and update episode laughter_pct."""
    with sqlite3.connect(DB_PATH) as conn:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS laughter_frames (
                episode_number INTEGER NOT NULL,
                time_seconds REAL NOT NULL,
                score REAL NOT NULL,
                PRIMARY KEY (episode_number, time_seconds),
                FOREIGN KEY (episode_number) REFERENCES episodes(episode_number)
            )
        """)

        # Clear old data for this episode
        conn.execute("DELETE FROM laughter_frames WHERE episode_number = ?", (episode_number,))

        # Insert per-second scores (already per-second from event-based detection)
        rows = []
        for w in windows:
            sec = w.get("w", 0)
            score = w.get("s", 0)
            rows.append((episode_number, float(sec), float(score)))

        conn.executemany(
            "INSERT OR REPLACE INTO laughter_frames (episode_number, time_seconds, score) VALUES (?, ?, ?)",
            rows,
        )

        # Compute laughter_pct — use total_duration if provided, else estimate from data
        active_seconds = sum(1 for _, _, s in rows if s > 0)
        laugh_count = sum(1 for w in windows if w.get("s", 0) > 0)
        if total_duration <= 0:
            total_duration = (max((w.get("w", 0) for w in windows), default=0) + 1) if windows else 1
        laughter_pct = round((active_seconds / total_duration) * 100, 2) if total_duration > 0 else 0.0

        conn.execute(
            "UPDATE episodes SET laughter_pct = ?, laugh_count = ? WHERE episode_number = ?",
            (laughter_pct, laugh_count, episode_number),
        )
        conn.commit()

    log.info(f"  Saved {len(rows)} laughter frames, laughter_pct={laughter_pct:.1f}%, laugh_windows={laugh_count}")


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


def fix_golden_ticket_status():
    """Correct golden ticket and status fields across the full sets table.

    Two fixes, safe to run repeatedly:
    1. If a comedian won the golden ticket in episode N, any later episode that also
       has golden_ticket=True is a duplicate — clear it and relabel as regular.
    2. If a comedian has ever appeared as 'regular', any later appearance as
       'bucket_pull' is a mislabel — correct it to 'regular'. Once a regular,
       always a regular.
    """
    with sqlite3.connect(DB_PATH) as conn:
        # Fix 1: duplicate golden tickets — keep only the first win
        conn.execute("""
            UPDATE sets
            SET golden_ticket = 0,
                status        = 'regular',
                kill_score    = MAX(0, kill_score - 10)
            WHERE set_id IN (
                SELECT set_id FROM (
                    SELECT set_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY comedian_name
                               ORDER BY episode_number ASC
                           ) AS rn
                    FROM sets
                    WHERE golden_ticket = 1
                )
                WHERE rn > 1
            )
        """)
        fix1 = conn.execute("SELECT changes()").fetchone()[0]

        # Fix 2: past regulars incorrectly labeled as bucket_pull in later episodes
        conn.execute("""
            UPDATE sets
            SET status = 'regular'
            WHERE status = 'bucket_pull'
              AND EXISTS (
                SELECT 1 FROM sets s2
                WHERE s2.comedian_name = sets.comedian_name
                  AND s2.status = 'regular'
                  AND s2.episode_number < sets.episode_number
              )
        """)
        fix2 = conn.execute("SELECT changes()").fetchone()[0]

        conn.commit()

    if fix1:
        log.info(f"fix_golden_ticket_status: corrected {fix1} duplicate GT win(s)")
    if fix2:
        log.info(f"fix_golden_ticket_status: corrected {fix2} past-regular-as-bucket_pull mislabel(s)")


def save_episode(yt_info: dict, transcript: list[dict], analysis: dict, guests: list[str]):
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
            (episode_number, title, date, venue, youtube_url, video_id, guests,
             status, pipeline_version,
             laugh_count, laughter_pct, view_count, like_count, comment_count, upload_date, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'done', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_number,
            yt_info.get("title", ""),
            yt_info.get("upload_date"),
            ep_data.get("venue"),
            f"https://www.youtube.com/watch?v={yt_info['video_id']}",
            yt_info["video_id"],
            json.dumps(guests),  # from title extraction, NOT transcript
            PIPELINE_VERSION,
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
            start = s.get("set_start_seconds")
            end = s.get("set_end_seconds")

            conn.execute("""
                INSERT OR REPLACE INTO sets
                (set_id, episode_number, set_number, comedian_name, status, set_transcript,
                 set_start_seconds, set_end_seconds,
                 topic_tags, crowd_reaction, tony_praise_level,
                 golden_ticket, sign_up_again, promoted_to_regular,
                 invited_secret_show, joke_book_size, interview_summary, kill_score,
                 disclosed_age, disclosed_occupation, disclosed_location,
                 disclosed_relationship_status, disclosed_years_doing_comedy,
                 fun_facts)
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
                json.dumps(s.get("topic_tags", [])),
                s.get("crowd_reaction"),
                s.get("tony_praise_level"),
                1 if s.get("golden_ticket") else 0,
                1 if s.get("sign_up_again") else 0,
                1 if s.get("promoted_to_regular") else 0,
                1 if s.get("invited_secret_show") else 0,
                s.get("joke_book_size"),
                s.get("interview_summary"),
                kill_score,
                s.get("disclosed_age"),
                s.get("disclosed_occupation"),
                s.get("disclosed_location"),
                s.get("disclosed_relationship_status"),
                s.get("disclosed_years_doing_comedy"),
                json.dumps(s.get("fun_facts", [])),
            ))

        conn.commit()

    log.info(f"Saved episode #{episode_number}: {len(analysis.get('sets', []))} sets, {laugh_count} laughs")
    fix_golden_ticket_status()


# ---------------------------------------------------------------------------
# Episode tracking
# ---------------------------------------------------------------------------

def load_episodes() -> list[dict]:
    with open(EPISODES_JSON) as f:
        return json.load(f)["episodes"]


def update_episode_status(episode_number: int, status: str, error: str | None = None):
    # Update episodes.json (legacy, kept for compatibility)
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

    # Update DB status
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            if status == "done":
                conn.execute(
                    "UPDATE episodes SET status = ?, pipeline_version = ? WHERE episode_number = ?",
                    (status, PIPELINE_VERSION, episode_number),
                )
            else:
                conn.execute(
                    "UPDATE episodes SET status = ? WHERE episode_number = ?",
                    (status, episode_number),
                )


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def sync_db_to_railway():
    """Push the local SQLite DB to Railway via /admin/upload-db. Skips silently if not configured."""
    backend_url = os.getenv("RAILWAY_BACKEND_URL", "").rstrip("/")
    admin_secret = os.getenv("ADMIN_SECRET", "")
    if not backend_url or not admin_secret:
        return

    try:
        with open(DB_PATH, "rb") as f:
            db_bytes = f.read()

        boundary = "killtony_boundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="kill_tony.db"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + db_bytes + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{backend_url}/admin/upload-db",
            data=body,
            headers={
                "x-admin-secret": admin_secret,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            log.info(f"Railway DB synced: {resp.read().decode()}")
    except Exception as e:
        log.warning(f"Railway sync failed (non-fatal): {e}")


def process_episode(client: genai.Client, ep: dict):
    episode_number = ep["episode_number"]
    url = ep["url"]
    log.info(f"{'='*60}")
    log.info(f"Processing episode #{episode_number}: {ep['title']}")
    log.info(f"{'='*60}")

    # Validate before processing
    title = ep.get("title", "")
    duration = ep.get("duration_seconds")
    if not is_valid_episode(title, duration):
        log.warning(f"  Skipping: not a valid episode (no ep# or under 1hr). Title: '{title}', Duration: {duration}s")
        update_episode_status(episode_number, "skipped")
        return

    update_episode_status(episode_number, "processing")

    # Get YouTube stats
    log.info("Fetching YouTube metadata...")
    yt_info = get_youtube_info(url)
    log.info(f"  Views: {yt_info.get('view_count', 'N/A'):,} | Likes: {yt_info.get('like_count', 'N/A'):,} | Comments: {yt_info.get('comment_count', 'N/A'):,}")

    # Extract guests from YouTube title
    log.info("Extracting guests from title...")
    guests = extract_guests_from_title(client, ep.get("title", ""))

    # Download audio and split into chunks
    audio_path = download_audio(url, episode_number)
    chunk_paths, chunk_offsets = split_into_chunks(audio_path, episode_number)

    # Pass 1: Transcribe (chunked)
    transcript = pass1_transcribe(client, chunk_paths, chunk_offsets)

    # Pass 2: Analyze
    analysis = pass2_analyze(client, transcript, episode_number)

    # Save to SQLite
    save_episode(yt_info, transcript, analysis, guests)

    # Laughter detection (2.5 Pro, uses full audio file)
    try:
        laughter_windows, laughter_duration = detect_laughter(client, audio_path, episode_number)
        save_laughter_frames(episode_number, laughter_windows, laughter_duration)
    except Exception as e:
        log.warning(f"Laughter detection failed for ep #{episode_number} (non-fatal): {e}")

    # Summary
    sets = analysis.get("sets", [])
    log.info(f"Episode #{episode_number} complete: {len(sets)} sets extracted")
    for s in sets:
        ks = compute_kill_score(s)
        log.info(f"  #{s.get('set_number')}: {s.get('comedian_name')} ({s.get('status')}) — kill_score={ks:.1f}")

    update_episode_status(episode_number, "done")
    sync_db_to_railway()

    # Clean up audio to save disk space (transcript is kept for reprocess_pass2)
    audio_dir = AUDIO_CACHE_DIR / f"ep_{episode_number}"
    if audio_dir.exists():
        import shutil
        shutil.rmtree(audio_dir)
        log.info(f"Cleaned up audio cache for episode #{episode_number}")


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


def fix_missing_guests():
    """Backfill empty guest lists from YouTube titles using regex (no API call)."""
    episodes = load_episodes()
    title_map = {ep["episode_number"]: ep.get("title", "") for ep in episodes}

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT episode_number, guests FROM episodes").fetchall()

    fixed = 0
    for row in rows:
        ep_num = row["episode_number"]
        current_guests = json.loads(row["guests"]) if row["guests"] else []
        if current_guests:
            continue
        title = title_map.get(ep_num, "")
        if not title:
            continue
        new_guests = extract_guests_from_title_regex(title)
        if new_guests:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE episodes SET guests = ? WHERE episode_number = ?",
                             (json.dumps(new_guests), ep_num))
            print(f"  Fixed ep #{ep_num}: {new_guests}")
            fixed += 1
        else:
            print(f"  Skipped ep #{ep_num}: no guests found in title '{title}'")

    print(f"\nFixed {fixed} episode(s)")


def main():
    parser = argparse.ArgumentParser(description="Kill Tony batch processor")
    parser.add_argument("--episode", type=int, help="Process a specific episode number")
    parser.add_argument("--status", action="store_true", help="Show processing status")
    parser.add_argument("--fix-guests", action="store_true",
                        help="Backfill missing guest names from YouTube titles (no API needed)")
    parser.add_argument("--fix-golden-tickets", action="store_true",
                        help="Correct past GT winners: only first win keeps golden_ticket=True, rest become regulars")
    parser.add_argument("--limit", type=int, help="Max number of episodes to process in this run")
    parser.add_argument("--laughter-only", action="store_true",
                        help="Run laughter detection only on already-processed episodes (requires cached audio)")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.fix_guests:
        fix_missing_guests()
        return

    if args.fix_golden_tickets:
        init_db()
        fix_golden_ticket_status()
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not found in .env")
        sys.exit(1)

    init_db()
    client = genai.Client(api_key=api_key)
    episodes = load_episodes()

    if args.laughter_only:
        done_eps = sorted(
            [e for e in episodes if e.get("status") == "done"],
            key=lambda e: e["episode_number"],
            reverse=True,
        )
        if args.episode:
            done_eps = [e for e in done_eps if e["episode_number"] == args.episode]
        if args.limit:
            done_eps = done_eps[:args.limit]
        log.info(f"Running laughter detection on {len(done_eps)} episodes ({LAUGHTER_MODEL})")
        for i, ep in enumerate(done_eps):
            ep_num = ep["episode_number"]
            audio_dir = AUDIO_CACHE_DIR / f"ep_{ep_num}"
            audio_path = audio_dir / "full.mp3"
            if not audio_path.exists():
                # Need to re-download
                log.info(f"[{i+1}/{len(done_eps)}] Downloading audio for ep #{ep_num}...")
                try:
                    audio_path = download_audio(ep["url"], ep_num)
                except Exception as e:
                    log.error(f"  Download failed for ep #{ep_num}: {e}")
                    continue
            log.info(f"[{i+1}/{len(done_eps)}] Laughter detection for ep #{ep_num}")
            try:
                windows, duration = detect_laughter(client, audio_path, ep_num)
                save_laughter_frames(ep_num, windows, duration)
            except Exception as e:
                log.error(f"  Laughter detection failed for ep #{ep_num}: {e}")
                continue
        sync_db_to_railway()
        return

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

    # Process all pending episodes, newest first
    pending = sorted(
        [e for e in episodes if e.get("status") == "pending"],
        key=lambda e: e["episode_number"],
        reverse=True
    )
    if args.limit:
        pending = pending[:args.limit]
    if not pending:
        log.info("No pending episodes to process.")
        show_status()
        return

    total_chunks_est = sum(max(1, e["duration_seconds"] // (CHUNK_MINUTES * 60 - OVERLAP_MINUTES * 60) + 1) for e in pending)
    total_calls_est = total_chunks_est + len(pending) * 2  # chunks + 1 pass2 + 1 laughter per episode
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
