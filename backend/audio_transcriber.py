"""
Audio transcription using Gemini 3.1 Flash Lite.

Simple, fast, and reliable transcription by:
1. Downloading audio from YouTube
2. Converting to MP3 for faster processing
3. Uploading to Gemini Files API
4. Getting transcript via Gemini 3.1 Flash Lite
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from yt_dlp import YoutubeDL

# Load .env from root directory
root_env = Path(__file__).parent.parent / ".env"
if root_env.exists():
    load_dotenv(root_env)


class AudioTranscriptionError(RuntimeError):
    pass


def transcribe_youtube_audio(
    youtube_url: str,
    *,
    model: str = "gemini-3.1-flash-lite-preview",
) -> list[dict[str, Any]]:
    """
    Transcribe YouTube video audio using Gemini 3.1 Flash Lite.

    Returns a list of transcript entries, each with:
    - start: float (seconds)
    - duration: float (seconds)
    - text: str (spoken words)
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise AudioTranscriptionError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

    with tempfile.TemporaryDirectory(prefix="kt_") as tmpdir:
        tmp_path = Path(tmpdir)

        # Download and convert audio
        print("Downloading audio from YouTube...")
        audio_path = _download_and_convert_audio(youtube_url, tmp_path)

        # Upload and transcribe
        client = genai.Client(api_key=api_key)
        print(f"Uploading {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f}MB)...")
        uploaded = client.files.upload(path=audio_path)

        try:
            # Wait for file to be ready
            print("Waiting for Gemini to process file...")
            _wait_for_active(client, uploaded.name)

            # Transcribe
            print(f"Transcribing with {model}...")
            response = client.models.generate_content(
                model=model,
                contents=[
                    (
                        "Transcribe this audio. Return ONLY valid JSON (no other text). "
                        "Format: an array of objects with keys: start_seconds, end_seconds, text. "
                        "Each number is a float, each text is a string. "
                        "Include all spoken words. Be precise with timestamps. "
                        "Example format: [{\"start_seconds\": 0, \"end_seconds\": 5, \"text\": \"hello\"}]"
                    ),
                    uploaded,
                ],
            )

            # Parse response - be flexible with JSON parsing
            import re
            transcript_text = response.text.strip()

            # Remove markdown code blocks if present
            if transcript_text.startswith("```"):
                transcript_text = transcript_text.lstrip("`").lstrip("json").lstrip("\n")
                transcript_text = transcript_text.rstrip("`").rstrip("\n").strip()

            # Collapse line breaks and extra whitespace first (common in LLM JSON responses)
            # Replace newlines with spaces, then normalize multiple spaces
            transcript_text = transcript_text.replace("\n", " ").replace("\r", "")
            transcript_text = re.sub(r"\s+", " ", transcript_text).strip()

            # Extract the JSON array - find the complete array and ignore trailing junk
            if not transcript_text.startswith("["):
                match = re.search(r"\[.*?\]", transcript_text, re.DOTALL)
                if match:
                    transcript_text = match.group(0)
            else:
                # Find the matching closing bracket for the opening one
                # This handles responses that have extra junk after the JSON
                depth = 0
                end_pos = 0
                for i, char in enumerate(transcript_text):
                    if char == "[":
                        depth += 1
                    elif char == "]":
                        depth -= 1
                        if depth == 0:
                            end_pos = i + 1
                            break
                if end_pos > 0:
                    transcript_text = transcript_text[:end_pos]

            try:
                payload = json.loads(transcript_text)
            except json.JSONDecodeError as e:
                # Try to fix common JSON issues
                # 1. Gemini sometimes includes extra fields - sanitize those
                transcript_text = _sanitize_json_response(transcript_text)

                # 2. Timestamps in MM:SS.MS format - convert to seconds
                transcript_text = _convert_timestamp_format(transcript_text)

                # 3. Fix missing closing brackets
                if transcript_text.count("[") > transcript_text.count("]"):
                    transcript_text += "]" * (transcript_text.count("[") - transcript_text.count("]"))

                try:
                    payload = json.loads(transcript_text)
                except json.JSONDecodeError:
                    # If still failing, show error details
                    error_pos = e.pos
                    context_start = max(0, error_pos - 100)
                    context_end = min(len(transcript_text), error_pos + 100)
                    context = transcript_text[context_start:context_end]
                    raise AudioTranscriptionError(
                        f"Failed to parse Gemini JSON response: {e}\n"
                        f"Error at position {error_pos}\n"
                        f"Context: ...{context}...\n"
                        f"Full response (first 500 chars): {response.text[:500]}"
                    ) from e

            if not isinstance(payload, list):
                raise AudioTranscriptionError("Response was not a JSON array")

            # Convert to standard format
            entries = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                start = float(item.get("start_seconds", 0))
                end = float(item.get("end_seconds", start))
                text = str(item.get("text", "")).strip()
                if text:
                    entries.append({
                        "start": start,
                        "duration": max(0.0, end - start),
                        "text": text,
                    })

            entries.sort(key=lambda x: x["start"])
            print(f"Extracted {len(entries)} transcript entries")
            return entries

        finally:
            # Clean up
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass


def _sanitize_json_response(json_text: str) -> str:
    """
    Remove invalid/extra fields from Gemini JSON response.

    Gemini sometimes includes extra fields like "box_2d", "label", etc.
    This extracts only valid transcript entries with start_seconds, end_seconds, text.
    """
    import re

    # Find all objects that have start_seconds/end_seconds/text
    # Pattern: {...start_seconds...end_seconds...text...}
    # This is tricky because we need to handle nested braces properly

    # Simpler approach: rebuild the JSON from scratch by extracting valid entries
    # Find all patterns like {"start_seconds": X, "end_seconds": Y, "text": Z, ...}
    # and rebuild with only the fields we want

    entries = []

    # Look for start_seconds values
    start_pattern = r'"start_seconds"\s*:\s*([\d.]+)'
    end_pattern = r'"end_seconds"\s*:\s*([\d.:]+)'
    text_pattern = r'"text"\s*:\s*"([^"]*(?:\\"[^"]*)*)"'

    # Find all start_seconds positions
    for start_match in re.finditer(start_pattern, json_text):
        start_pos = start_match.start()
        start_sec = start_match.group(1)

        # Find the next end_seconds after this position
        end_match = re.search(end_pattern, json_text[start_pos:])
        if not end_match:
            continue

        end_sec = end_match.group(1)
        end_pos = start_pos + end_match.start()

        # Find text field between these two (or shortly after end_seconds)
        text_match = re.search(text_pattern, json_text[end_pos:])
        if not text_match:
            continue

        text = text_match.group(1)

        # Try to parse the numbers (handle timestamp format)
        try:
            if ':' in start_sec:
                parts = start_sec.split(':')
                start_sec = str(int(parts[0]) * 60 + float(parts[1]))
            if ':' in end_sec:
                parts = end_sec.split(':')
                end_sec = str(int(parts[0]) * 60 + float(parts[1]))

            entries.append({
                "start_seconds": float(start_sec),
                "end_seconds": float(end_sec),
                "text": text.replace('\\"', '"')
            })
        except (ValueError, IndexError):
            continue

    # Rebuild as clean JSON
    if entries:
        return json.dumps(entries)

    # If that didn't work, return original (let the normal parser handle it)
    return json_text


def _convert_timestamp_format(json_text: str) -> str:
    """
    Convert timestamp format from MM:SS.MS to seconds.

    Gemini sometimes returns timestamps like "1:03.446" instead of 63.446.
    This converts them to numeric format for valid JSON.
    """
    import re

    # Pattern: "key": followed by MM:SS.MS format (not quoted)
    # e.g., "start_seconds": 1:03.446
    pattern = r'("(?:start_seconds|end_seconds)"\s*:\s*)(\d+):(\d{2})\.(\d+)'

    def convert_match(match):
        prefix = match.group(1)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        milliseconds = match.group(4)
        # Convert to total seconds: MM*60 + SS.MS
        total_seconds = minutes * 60 + seconds + float(f"0.{milliseconds}")
        return f'{prefix}{total_seconds}'

    return re.sub(pattern, convert_match, json_text)


def _download_and_convert_audio(youtube_url: str, output_dir: Path) -> Path:
    """Download audio from YouTube and convert to MP3."""
    # Download with yt-dlp
    outtmpl = str(output_dir / "audio.%(ext)s")
    opts = {
        "format": "251/bestaudio/best",
        "skip_download": False,
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
    }

    try:
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(youtube_url, download=True)
    except Exception as exc:
        raise AudioTranscriptionError(f"Download failed: {exc}") from exc

    # Find downloaded file
    downloaded_files = list(output_dir.glob("audio.*"))
    if not downloaded_files:
        raise AudioTranscriptionError("No audio file found after download")

    original_path = downloaded_files[0]

    # Convert to MP3 (makes Gemini processing much faster)
    mp3_path = output_dir / "audio.mp3"
    print("Converting to MP3...")
    try:
        subprocess.run(
            ["ffmpeg", "-i", str(original_path), "-q:a", "5", "-y", str(mp3_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
        original_path.unlink()
        return mp3_path
    except FileNotFoundError:
        raise AudioTranscriptionError("ffmpeg not found. Install with: brew install ffmpeg") from None
    except subprocess.CalledProcessError as exc:
        raise AudioTranscriptionError(f"MP3 conversion failed: {exc}") from exc


def _wait_for_active(client: genai.Client, file_name: str, timeout_seconds: int = 60) -> None:
    """Wait for file to become ACTIVE in Gemini Files API."""
    import time

    for attempt in range(timeout_seconds):
        try:
            file_info = client.files.get(name=file_name)
            if file_info.state == "ACTIVE":
                return
        except Exception:
            pass  # Ignore temporary errors

        if attempt < timeout_seconds - 1:
            time.sleep(1)

    raise AudioTranscriptionError(f"File did not become ACTIVE within {timeout_seconds} seconds")
