# Kill Tony Data Project

## Project Goal

Build a transcribed database of every Kill Tony 1-minute set, analyzed by Gemini, with the end goal of algorithmically identifying the **best Kill Tony minute of all time**. The database powers a public frontend at [killtonyarchive.com](https://killtonyarchive.com).

## What is Kill Tony?

Kill Tony is a weekly comedy podcast/show hosted by Tony Hinchcliffe where random comedians pull a golden ticket to perform a 1-minute stand-up set. After each set, they are interviewed by Tony and the house band/guests. The show has run for 700+ episodes.

## Tech Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite
- **Pipeline:** Gemini 2.5 Flash (Pass 1 audio transcription) + Gemini Flash Lite (Pass 2 text extraction)
- **Frontend:** SvelteKit + TypeScript
- **Hosting:** Railway

## Pipeline Overview (Two-Pass Chunked)

1. Download episode audio from YouTube (yt-dlp), convert to MP3 (ffmpeg)
2. Split into 20min overlapping chunks (3min overlap to avoid splitting sets)
3. **Pass 1:** Upload each chunk to Gemini → get speaker-labeled transcript
4. Merge chunks, deduplicate overlap regions, normalize speaker labels
5. **Pass 2:** Send full transcript text to Gemini → extract structured set data
6. Store in SQLite, expose via FastAPI

## Kill Score Formula Notes

The kill score formula is in `backend/batch_processor.py:compute_kill_score()`. If modifying it:
- **`joke_density` was removed** — unreliable due to subjective Gemini joke counts + WhisperX timestamp drift
- **YAMNet laughter-per-set** is a planned tiebreaker but blocked until WhisperX timestamps are accurate enough to correctly attribute laughter frames to set windows

## Website Testing & Screenshots

When asked to pull up a website for UI testing or analysis:
- **Default approach:** Use headless Playwright instances to take and analyze screenshots
- **Never:** Hijack/control the user's Chrome browser instance
- **Workflow:** Launch headless browser → navigate → take screenshot → read/analyze the image
