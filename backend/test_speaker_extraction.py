"""
Test script: Can Gemini identify speakers and extract structured set data
from a Kill Tony episode with context provided?

Uses a single episode to test the full schema extraction.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from yt_dlp import YoutubeDL

# Load .env from root directory
root_env = Path(__file__).parent.parent / ".env"
if root_env.exists():
    load_dotenv(root_env)


YOUTUBE_URL = "https://www.youtube.com/watch?v=6jytsJ8JIDk"

# Context we feed Gemini to help with speaker identification
EPISODE_CONTEXT = """
CONTEXT (use this to identify speakers):
- Host: Tony Hinchcliffe
- Co-host: Redban (Brian Redban)
- This is a Kill Tony episode — a live comedy podcast where audience members
  pull a golden ticket to perform a 1-minute stand-up set, then get interviewed.
- After each set, Tony and the guest judges give feedback.
- Redban sometimes gives a number rating and occasionally invites comedians
  to his "secret show."

If you can identify the guest judge(s) from the audio, label them as guest:<name>.
"""

EXTRACTION_PROMPT = """
You are analyzing a Kill Tony comedy podcast episode audio.

{context}

TASK: Transcribe and analyze this episode. Return ONLY valid JSON matching this schema:

{{
  "episode": {{
    "episode_number": number | null,
    "guests": ["guest name", ...],
    "venue": "string" | null
  }},
  "transcript": [
    {{
      "start_seconds": float,
      "end_seconds": float,
      "speaker": "tony | redban | guest:<name> | comedian:<name> | crowd | unknown",
      "text": "what was said"
    }}
  ],
  "sets": [
    {{
      "set_number": int,
      "comedian_name": "string",
      "status": "bucket_pull | regular | first_timer",
      "appearances": int | null,
      "topic_tags": ["string"],
      "joke_count": int | null,
      "crowd_reaction": "silence | light | moderate | big_laughs | roaring",
      "tony_praise_level": int (1-5) | null,
      "guest_feedback_sentiment": "positive | negative | neutral | none",
      "walked_off": boolean,
      "golden_ticket": boolean,
      "sign_up_again": boolean,
      "promoted_to_regular": boolean,
      "invited_secret_show": boolean,
      "joke_book_size": "none | small | medium | large",
      "set_transcript": "full text of their 1-min set",
      "interview_summary": "brief summary of the interview after their set"
    }}
  ]
}}

Rules:
- Label every speaker in the transcript using the format above.
- For comedians, use comedian:<their_name> as the speaker label.
- Extract ALL sets you can identify from the audio.
- For each set, pull as much data as possible. Use null for fields you can't determine.
- Be conservative with boolean fields — only set true if clearly stated/shown.
- topic_tags should be from: [self_deprecation, politics, relationships, sex, race, crowd_work, observational, shock_humor, storytelling, absurdist, physical, meta, regional, other]
"""


def download_audio(youtube_url: str, output_dir: Path, max_duration: int = 600) -> Path:
    """Download first N seconds of audio and convert to MP3."""
    outtmpl = str(output_dir / "audio.%(ext)s")
    opts = {
        "format": "251/bestaudio/best",
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "download_ranges": lambda info, ydl: [{"start_time": 0, "end_time": max_duration}],
    }

    print(f"Downloading first {max_duration}s of audio...")
    with YoutubeDL(opts) as ydl:
        ydl.extract_info(youtube_url, download=True)

    downloaded = list(output_dir.glob("audio.*"))
    if not downloaded:
        raise RuntimeError("No audio file found after download")

    original = downloaded[0]
    mp3_path = output_dir / "audio.mp3"
    print("Converting to MP3...")
    subprocess.run(
        ["ffmpeg", "-i", str(original), "-t", str(max_duration), "-q:a", "5", "-y", str(mp3_path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
    )
    original.unlink()
    return mp3_path


def main():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY in .env")
        return

    # Grab first 30 minutes
    max_duration = 1800

    with tempfile.TemporaryDirectory(prefix="kt_test_") as tmpdir:
        tmp_path = Path(tmpdir)
        audio_path = download_audio(YOUTUBE_URL, tmp_path, max_duration)

        client = genai.Client(api_key=api_key)
        print(f"Uploading {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f}MB)...")
        uploaded = client.files.upload(path=audio_path)

        try:
            # Wait for file to be ready
            import time
            for _ in range(60):
                file_info = client.files.get(name=uploaded.name)
                if file_info.state == "ACTIVE":
                    break
                time.sleep(1)

            prompt = EXTRACTION_PROMPT.format(context=EPISODE_CONTEXT)
            print("Sending to Gemini for analysis...")
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=[prompt, uploaded],
            )

            raw = response.text.strip()

            # Clean markdown fences if present
            if raw.startswith("```"):
                raw = raw.lstrip("`").lstrip("json").lstrip("\n")
                raw = raw.rstrip("`").rstrip("\n").strip()

            # Save raw response
            output_path = Path(__file__).parent / "test_output_speaker.json"
            try:
                data = json.loads(raw)
                with open(output_path, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"\nSaved structured output to {output_path}")

                # Print summary
                print(f"\n--- RESULTS ---")
                ep = data.get("episode", {})
                print(f"Episode: #{ep.get('episode_number', '?')}")
                print(f"Guests: {ep.get('guests', [])}")

                transcript = data.get("transcript", [])
                speakers = set(e.get("speaker", "unknown") for e in transcript)
                print(f"\nSpeakers identified: {sorted(speakers)}")
                print(f"Transcript entries: {len(transcript)}")

                # Show first few transcript entries
                print(f"\nFirst 10 transcript entries:")
                for entry in transcript[:10]:
                    print(f"  [{entry.get('start_seconds', 0):.1f}s] {entry.get('speaker', '?')}: {entry.get('text', '')[:80]}")

                sets = data.get("sets", [])
                print(f"\nSets found: {len(sets)}")
                for s in sets:
                    print(f"  #{s.get('set_number')}: {s.get('comedian_name')} ({s.get('status')})")
                    print(f"    Topics: {s.get('topic_tags', [])}")
                    print(f"    Crowd: {s.get('crowd_reaction')} | Tony: {s.get('tony_praise_level')}/5")
                    print(f"    Book: {s.get('joke_book_size')} | Golden ticket: {s.get('golden_ticket')}")
                    print(f"    Sign up again: {s.get('sign_up_again')} | Secret show: {s.get('invited_secret_show')}")
                    print()

            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
                output_path = Path(__file__).parent / "test_output_speaker_raw.txt"
                with open(output_path, "w") as f:
                    f.write(raw)
                print(f"Saved raw response to {output_path}")

        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass


if __name__ == "__main__":
    main()
