#!/usr/bin/env python3
"""
Test Gemini 3.1 Flash Lite for YouTube audio transcription.
This is a simplified, cleaner approach compared to chunking.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from google import genai


def transcribe_youtube_with_gemini_flash_lite(
    youtube_url: str,
    *,
    model: str = "gemini-3.1-flash-lite-preview",
) -> list[dict[str, Any]]:
    """
    Transcribe YouTube audio using Gemini 3.1 Flash Lite.

    This approach:
    1. Downloads audio from YouTube
    2. Uploads to Gemini Files API
    3. Sends to Gemini for transcription with timestamps

    Returns transcript as list of dicts with start, duration, text.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

    with tempfile.TemporaryDirectory(prefix="kt_") as tmpdir:
        tmp_path = Path(tmpdir)

        # Download audio
        print(f"Downloading audio from {youtube_url}...")
        audio_path = _download_audio(youtube_url, tmp_path)
        print(f"Downloaded to {audio_path.name}")

        # Upload to Gemini
        print(f"Uploading {audio_path.name} to Gemini Files API...")
        client = genai.Client(api_key=api_key)
        uploaded = client.files.upload(path=audio_path)
        print(f"Uploaded successfully")

        # Wait for file to be ready with retries
        import time
        max_retries = 300  # Try up to 300 times with 2 second intervals (10 minutes)
        for attempt in range(max_retries):
            try:
                file_info = client.files.get(name=uploaded.name)
                if file_info.state == "ACTIVE":
                    print(f"File is ACTIVE (attempt {attempt + 1})")
                    break
                else:
                    print(f"File state: {file_info.state} (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2)
            except Exception as e:
                # Ignore errors getting file state, just wait and retry
                if attempt < max_retries - 1:
                    time.sleep(2)
        else:
            raise RuntimeError("File did not become ACTIVE after 2 minutes")

        try:
            # Transcribe with Gemini 3.1 Flash Lite
            print(f"Transcribing with {model}...")
            response = client.models.generate_content(
                model=model,
                contents=[
                    (
                        "Transcribe this Kill Tony podcast audio. "
                        "Return ONLY a JSON array of objects with these exact keys: "
                        "start_seconds (number), end_seconds (number), text (string). "
                        "Include ALL spoken words. "
                        "Be precise with timestamps. "
                        "Output ONLY the JSON array, no markdown or explanation."
                    ),
                    uploaded,
                ],
            )

            transcript_text = response.text.strip()
            print(f"Got response from Gemini")

            # Parse response - remove markdown code blocks if present
            if transcript_text.startswith("```"):
                # Remove ```json or ``` at start
                transcript_text = transcript_text.lstrip("`").lstrip("json").lstrip("\n")
                # Remove ``` at end
                transcript_text = transcript_text.rstrip("`").rstrip("\n")

            import json
            payload = json.loads(transcript_text)

            # Convert to internal format
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
            # Clean up uploaded file
            try:
                client.files.delete(name=uploaded.name)
                print("Cleaned up uploaded file")
            except Exception as e:
                print(f"Warning: Could not delete uploaded file: {e}")


def _download_audio(youtube_url: str, output_dir: Path) -> Path:
    """Download audio from YouTube using yt-dlp and convert to MP3."""
    outtmpl = str(output_dir / "%(id)s.%(ext)s")
    opts = {
        "format": "251/bestaudio/best",
        "skip_download": False,
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
    }

    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            file_path = Path(ydl.prepare_filename(info))
    except Exception as exc:
        raise RuntimeError(f"Audio download failed: {exc}") from exc

    if not file_path.exists():
        raise RuntimeError(f"Audio file not found after download: {file_path}")

    # Convert to MP3 for faster processing
    import subprocess
    mp3_path = file_path.with_suffix(".mp3")
    print(f"Converting to MP3...")
    try:
        subprocess.run(
            ["ffmpeg", "-i", str(file_path), "-q:a", "5", "-y", str(mp3_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
        file_path.unlink()  # Delete original
        return mp3_path
    except Exception as e:
        print(f"Warning: MP3 conversion failed, using original: {e}")
        return file_path


if __name__ == "__main__":
    # Test with Kill Tony episode
    # Using a URL you can provide
    youtube_url = os.getenv(
        "KILL_TONY_URL",
        "https://www.youtube.com/watch?v=test"  # Replace with actual URL
    )

    print(f"Transcribing: {youtube_url}\n")

    try:
        transcript = transcribe_youtube_with_gemini_flash_lite(youtube_url)
        print(f"\n{'='*70}")
        print(f"SUCCESS! Got {len(transcript)} entries")
        print(f"{'='*70}")
        if transcript:
            print(f"\nFirst 3 entries:")
            for entry in transcript[:3]:
                print(f"  [{entry['start']:.1f}s] {entry['text'][:80]}...")
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"ERROR: {type(e).__name__}")
        print(f"{'='*70}")
        print(f"{e}")
