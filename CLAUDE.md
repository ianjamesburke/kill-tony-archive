# Kill Tony Archive

## Project Goal

Build a transcribed database of every Kill Tony 1-minute set, analyzed by Gemini, with the end goal of algorithmically identifying the **best Kill Tony minute of all time**. The database powers a public frontend at [killtonyarchive.com](https://killtonyarchive.com).

## What is Kill Tony?

Kill Tony is a weekly comedy podcast/show hosted by Tony Hinchcliffe where random comedians pull a golden ticket to perform a 1-minute stand-up set. After each set, they are interviewed by Tony and the house band/guests. The show has run for 760+ episodes. New episodes drop every Monday night.

## Current Stats

510 episodes indexed, 835 sets transcribed, 593 comedians tracked.

## Tech Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite (`data/kill_tony.db`)
- **Pipeline:** Gemini 3.1 Flash Lite (Pass 1 audio transcription, fallback to Gemini 3 Flash) + Gemini Flash Lite (Pass 2 text extraction)
- **Frontend:** SvelteKit + TypeScript
- **Hosting:** Railway (separate frontend + backend services)

## Deploy

- **Frontend:** `cd frontend && railway up --detach` (linked to kill-tony-frontend service)
- **Backend:** `cd backend && railway up --detach` (linked to kill-tony-backend service)
- Railway CLI must be linked per-directory (`railway link` from within `frontend/` and `backend/` separately)
- Both are linked on the Linux dev machine

## SEO

- All pages have unique titles, meta descriptions, OG tags, Twitter cards, canonical URLs
- `og:image`: YouTube thumbnails for episode pages, `frontend/static/og-default.png` as default
- `sitemap.xml` auto-generated at `/sitemap.xml`
- `robots.txt` references sitemap
- Google Search Console verified (meta tag in `+layout.svelte`), sitemap submitted
- Google verification tag: `Ijw_g4PxOeP3R-lvxju2alLphAjsixAm6V9xDQZPaSc`

## Pipeline Overview (Two-Pass Chunked)

1. Download episode audio from YouTube (yt-dlp), convert to MP3 (ffmpeg)
2. Split into 20min overlapping chunks (3min overlap to avoid splitting sets)
3. **Pass 1:** Upload each chunk to Gemini → get speaker-labeled transcript
4. Merge chunks, deduplicate overlap regions, normalize speaker labels
5. **Pass 2:** Send full transcript text to Gemini → extract structured set data
6. Store in SQLite, expose via FastAPI
7. Model fallback: flash-lite (4 attempts) → flash (3 attempts) per chunk
8. Episodes with 3+ consecutive failures are auto-skipped until pipeline version bumps

## Kill Score Formula Notes

The kill score formula is in `backend/batch_processor.py:compute_kill_score()`. If modifying it:
- **`joke_density` was removed** — unreliable due to subjective Gemini joke counts + WhisperX timestamp drift
- **YAMNet laughter-per-set** is a planned tiebreaker but blocked until WhisperX timestamps are accurate enough to correctly attribute laughter frames to set windows

## Key Files

- `justfile` — dev commands, pipeline commands, deploy
- `DEV_LOG.md` — architectural decisions and session work logs
- `backend/batch_processor.py` — main pipeline processor
- `backend/daily_processor.py` — systemd-triggered daily processing
- `backend/qa_checks.py` — QA validation for processed episodes
- `frontend/src/routes/+layout.svelte` — global layout, nav, meta tags, Google verification
- `frontend/static/og-default.png` — default Open Graph image
- `frontend/static/robots.txt` — crawler directives
