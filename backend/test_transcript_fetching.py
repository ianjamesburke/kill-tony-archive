#!/usr/bin/env python3
"""Test which transcript fetching methods work with a real Kill Tony episode."""

import os
import sys
from transcript_fetcher import extract_video_id, _fetch_with_youtube_transcript_api, _fetch_with_yt_dlp
from audio_transcriber import transcribe_youtube_audio_with_gemini

# A real Kill Tony episode - you can override with environment variable
# Using Kill Tony main channel - will search for a recent episode
KILL_TONY_URL = os.getenv("KILL_TONY_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # Example

def test_youtube_transcript_api(video_id: str) -> bool:
    """Test YouTube Transcript API approach."""
    print("\n" + "="*60)
    print("TEST 1: YouTube Transcript API")
    print("="*60)
    try:
        entries = _fetch_with_youtube_transcript_api(video_id)
        print(f"✓ SUCCESS - Got {len(entries)} transcript entries")
        if entries:
            print(f"  Sample: {entries[0]}")
        return True
    except Exception as e:
        print(f"✗ FAILED - {type(e).__name__}: {e}")
        return False


def test_yt_dlp(url: str) -> bool:
    """Test yt-dlp approach."""
    print("\n" + "="*60)
    print("TEST 2: yt-dlp")
    print("="*60)
    try:
        entries = _fetch_with_yt_dlp(url)
        print(f"✓ SUCCESS - Got {len(entries)} transcript entries")
        if entries:
            print(f"  Sample: {entries[0]}")
        return True
    except Exception as e:
        print(f"✗ FAILED - {type(e).__name__}: {e}")
        return False


def test_gemini_audio(url: str) -> bool:
    """Test Gemini audio transcription approach."""
    print("\n" + "="*60)
    print("TEST 3: Gemini Audio Transcription (may take a while)")
    print("="*60)
    try:
        # This will take a while and requires GEMINI_API_KEY
        entries = transcribe_youtube_audio_with_gemini(url)
        print(f"✓ SUCCESS - Got {len(entries)} transcript entries")
        if entries:
            print(f"  Sample: {entries[0]}")
        return True
    except Exception as e:
        print(f"✗ FAILED - {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print(f"Testing transcript fetching with: {KILL_TONY_URL}")

    try:
        video_id = extract_video_id(KILL_TONY_URL)
        print(f"Extracted video ID: {video_id}\n")
    except Exception as e:
        print(f"ERROR: Could not extract video ID: {e}")
        sys.exit(1)

    results = {
        "YouTube Transcript API": test_youtube_transcript_api(video_id),
        "yt-dlp": test_yt_dlp(KILL_TONY_URL),
        "Gemini Audio": test_gemini_audio(KILL_TONY_URL),
    }

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for method, success in results.items():
        status = "✓ WORKS" if success else "✗ FAILS"
        print(f"{method}: {status}")
