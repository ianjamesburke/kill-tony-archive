"""
Simple transcript downloader: YouTube URL → Plain text file.

Usage:
    python transcript_downloader.py <youtube_url>
    python transcript_downloader.py "https://www.youtube.com/watch?v=Xdtk8hgxbik"
"""

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL

from audio_transcriber import transcribe_youtube_audio


def extract_video_id(youtube_url: str) -> str:
    """Extract video ID from YouTube URL."""
    parsed = urlparse(youtube_url)

    if parsed.hostname in {"youtu.be"}:
        video_id = parsed.path.lstrip("/")
        if video_id:
            return video_id

    if parsed.hostname and "youtube.com" in parsed.hostname:
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            video_id = query.get("v", [""])[0]
            if video_id:
                return video_id

    raise ValueError(f"Could not extract video ID from: {youtube_url}")


def get_episode_number_and_title(youtube_url: str) -> tuple[str | None, str]:
    """
    Get video title and extract Kill Tony episode number if present.

    Returns:
        Tuple of (episode_number or None, full_title)
        e.g., ("589", "KILL TONY #589 - RON WHITE")
    """
    opts = {"quiet": True, "no_warnings": True}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            title = info.get("title", "")

            # Try to extract episode number from title
            # Matches "KILL TONY #589" or similar
            match = re.search(r"#(\d+)", title)
            episode_num = match.group(1) if match else None

            return episode_num, title
    except Exception as e:
        raise ValueError(f"Could not fetch video metadata: {e}")


def download_transcript(youtube_url: str, output_dir: Path = None) -> Path:
    """
    Download transcript and save as plain text.

    Args:
        youtube_url: YouTube video URL
        output_dir: Directory to save transcript (default: data/transcripts/)

    Returns:
        Path to saved transcript file
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "transcripts"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video ID and episode info
    video_id = extract_video_id(youtube_url)
    episode_num, title = get_episode_number_and_title(youtube_url)

    # Download transcript
    print(f"Downloading transcript for: {title}")
    entries = transcribe_youtube_audio(youtube_url)

    # Save as plain text with episode number if available
    if episode_num:
        filename = f"KT#{episode_num}.txt"
    else:
        filename = f"{video_id}.txt"

    output_file = output_dir / filename
    print(f"Saving transcript to {output_file}")

    with open(output_file, "w") as f:
        for entry in entries:
            text = entry["text"]
            f.write(f"{text}\n")

    print(f"✓ Saved {len(entries)} transcript entries to {output_file}")
    return output_file


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python transcript_downloader.py <youtube_url>")
        print("Example: python transcript_downloader.py https://www.youtube.com/watch?v=Xdtk8hgxbik")
        sys.exit(1)

    youtube_url = sys.argv[1]

    try:
        transcript_file = download_transcript(youtube_url)
        print(f"\n✓ Complete! Transcript saved to: {transcript_file}")
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
