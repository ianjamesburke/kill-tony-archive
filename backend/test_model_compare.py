"""
Quick test: Run one chunk of one episode with gemini-2.5-flash
to compare quality against gemini-3-flash-preview.
"""
import json
import sys

from pathlib import Path

from dotenv import load_dotenv
from google import genai

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# Import pipeline utilities from batch_processor
from batch_processor import (
    PASS1_PROMPT,
    _parse_json_array,
    download_audio,
    normalize_speaker,
    split_into_chunks,
    upload_and_wait,
)

MODEL_25_FLASH = "gemini-2.5-flash"
MODEL_3_FLASH = "gemini-3-flash-preview"


def test_one_chunk(model_name: str, chunk_path: Path, chunk_num: int = 1, offset_seconds: int = 0):
    """Transcribe a single chunk with the given model and return entries."""
    client = genai.Client()
    print(f"\n{'='*60}")
    print(f"Testing model: {model_name}")
    print(f"Chunk: {chunk_path.name}")
    print(f"{'='*60}")

    uploaded = upload_and_wait(client, chunk_path)
    try:
        prompt = PASS1_PROMPT.format(
            chunk_num=chunk_num,
            offset_seconds=offset_seconds,
            offset_str=f"{offset_seconds // 60}:{offset_seconds % 60:02d}",
        )
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, uploaded],
            config={"http_options": {"timeout": 600000}},
        )
        entries = _parse_json_array((response.text or "").strip())

        # Normalize speakers
        for entry in entries:
            entry["speaker"] = normalize_speaker(entry.get("speaker", "unknown"))

        print(f"  Entries returned: {len(entries)}")
        speakers = {}
        for e in entries:
            s = e.get("speaker", "unknown")
            speakers[s] = speakers.get(s, 0) + 1
        print(f"  Speaker breakdown: {json.dumps(speakers, indent=2)}")

        # Show first 5 and last 5 entries
        print(f"\n  First 5 entries:")
        for e in entries[:5]:
            print(f"    [{e.get('start_seconds',0)}s] {e.get('speaker','?')}: {e.get('text','')[:80]}")
        print(f"\n  Last 5 entries:")
        for e in entries[-5:]:
            print(f"    [{e.get('start_seconds',0)}s] {e.get('speaker','?')}: {e.get('text','')[:80]}")

        # Save full output
        out_path = ROOT / "data" / f"test_{model_name.replace('-', '_')}_chunk{chunk_num}.json"
        with open(out_path, "w") as f:
            json.dump(entries, f, indent=2)
        print(f"\n  Full output saved to: {out_path}")

        return entries
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass


def main():
    # Use episode 742 (already tested with 3-flash) or specify via CLI
    ep_num = int(sys.argv[1]) if len(sys.argv) > 1 else 742

    # Check if we already have audio cached
    from batch_processor import AUDIO_CACHE_DIR
    cached = list(AUDIO_CACHE_DIR.glob(f"ep{ep_num}_*.mp3")) if AUDIO_CACHE_DIR.exists() else []

    if cached:
        audio_path = cached[0]
        print(f"Using cached audio: {audio_path}")
    else:
        print(f"Downloading episode #{ep_num}...")
        import sqlite3
        from batch_processor import DB_PATH
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT youtube_url FROM episodes WHERE episode_number = ?", (ep_num,)).fetchone()
        if not row:
            print(f"Episode {ep_num} not found in DB")
            return
        audio_path = download_audio(row[0], ep_num)

    # Split into chunks, but we only use the first one
    chunk_paths, chunk_offsets = split_into_chunks(audio_path, ep_num)
    print(f"Total chunks: {len(chunk_paths)}, testing only chunk 1")

    chunk_path = chunk_paths[0]

    # Test with 2.5-flash (should have free tier quota)
    entries_25 = test_one_chunk(MODEL_25_FLASH, chunk_path, chunk_num=1, offset_seconds=chunk_offsets[0])

    print(f"\n\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"  gemini-2.5-flash:       {len(entries_25)} entries from chunk 1")
    print(f"  gemini-3-flash-preview: (see previous ep742 run — ~200+ entries per chunk)")


if __name__ == "__main__":
    main()
