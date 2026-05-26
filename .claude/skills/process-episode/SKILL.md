---
name: process-episode
description: "Process Kill Tony episodes through the full pipeline (download → WhisperX GPU transcription → Gemini extraction → SQLite) with auto-chunking for long episodes, age backfill, and post-processing QA."
risk: low
source: local
---

# Kill Tony Episode Processor

Process one or more Kill Tony episodes through the Pipeline v4 flow. All processing runs locally; Railway serves the read-only API.

## Trigger

Use this skill when the user says:
- `/process-episode <N>` — process a specific episode
- `/process-episode <YouTube URL>` — process by URL (extract episode number from title)
- `/reprocess-episode <N>` — re-run Pass 2 only (uses cached transcript)
- `/kt-qa <N>` — run QA checks only (no pipeline rerun)
- `/kt-status` — show pipeline status across all episodes
- `/kt-upload` — upload local DB to Railway
- Anything like "process episode 742", "run the pipeline for 758", "do this one too [URL]"

## Working Directory

All commands run from `~/Documents/GitHub/kill-tony-archive/`. Pipeline scripts are in `backend/`.

## Pipeline v4 Architecture

1. **Download** — yt-dlp downloads audio, ffmpeg converts to MP3
2. **Pass 1 (WhisperX on Modal GPU)** — T4 GPU transcription via Modal, ~$0.08/episode, returns word-level timestamps without speaker labels
3. **Pass 2 (Gemini Flash Lite)** — extracts structured set data (comedian names, topics, scores, etc.) from transcript text
4. **Auto-chunking** — episodes over 90 minutes automatically split Pass 2 into two halves with 5-minute overlap, deduplicating by comedian name
5. **Post-processing** — age backfill from prior appearances, golden ticket status fix, kill score computation
6. **QA** — automated set count + timecode spot-checks
7. **DB sync** — uploads SQLite to Railway via `/admin/upload-db`

## Commands Reference

```bash
# Via justfile:
just process 742       # Full pipeline: download → Pass 1 → Pass 2 → SQLite (includes QA)
just reprocess 742     # Pass 2 only (requires cached transcript from a prior run)
just qa 742            # QA checks only: set count + timecode spot-checks
just batch 5           # Process up to 5 pending episodes
just upload-db         # Upload local SQLite to Railway

# Direct script calls:
cd backend && uv run python batch_processor.py --episode 742     # Process single episode
cd backend && uv run python batch_processor.py --status          # Show all episode statuses
cd backend && uv run python qa_checks.py --episode 742           # Standalone QA run
```

## Process Episode (`/process-episode <N>`)

1. **Check status first:**
   ```
   ! cd ~/Documents/GitHub/kill-tony-archive/backend && uv run python batch_processor.py --status 2>/dev/null | grep -E "^\S+ +<N>"
   ```
   If already `done`, confirm with user before reprocessing (suggest `/reprocess-episode <N>` for Pass 2 only).

2. **Run the pipeline:**
   ```
   ! cd ~/Documents/GitHub/kill-tony-archive && just process <N>
   ```
   Takes 3-10 minutes. WhisperX on Modal GPU handles Pass 1 (~2 min for a 2hr episode). Pass 2 via Gemini is fast (~10s per call, or ~20s if auto-chunked). QA runs automatically at the end.

3. **On success:** Run the full QA suite (see below), then ask if they want to upload to Railway (`just upload-db`).

4. **On failure — common errors:**
   - `429 Resource Exhausted` / `RESOURCE_EXHAUSTED` — Gemini rate limit. Wait 60s and retry. Do NOT auto-loop.
   - `Function has not been hydrated` — Modal issue. Make sure `modal_whisperx.py` is importable and `app.run()` wraps the `.remote()` call.
   - `yt-dlp` / `Requested format is not available` — on macOS, Chrome cookies force a TV player path. The pipeline returns empty cookie opts on macOS to avoid this.
   - `Episode #N not found in database` — add it to the episodes table first.

## Pass 2 Auto-Chunking

Long episodes (>90 min of transcript) automatically split Pass 2 into two halves with a 5-minute overlap region. Sets are deduplicated by comedian name across the overlap. This prevents Gemini from truncating output and missing sets in the second half.

If an episode still shows fewer sets than expected after auto-chunking, the overlap may need manual adjustment. Check the transcript timestamps to see where sets fall relative to the midpoint.

## Age Backfill

After every `save_episode()`, the pipeline runs `backfill_comedian_ages()`:
- For each comedian in the episode with a NULL `disclosed_age`, checks if they have a known age from any prior appearance
- Uses the youngest known age as baseline (hallucinated ages from Gemini tend to be too high)
- Estimates birthday as 6 months before the reference episode date
- Calculates age for all NULL appearances based on elapsed time

## Reprocess Episode (`/reprocess-episode <N>`)

Runs Pass 2 only. Useful when the Pass 2 prompt was updated or extraction failed.

```
! cd ~/Documents/GitHub/kill-tony-archive && just reprocess <N>
```

Requires cached transcript at `backend/transcripts/ep_<N>.json`. If missing, run the full pipeline instead.

## QA Checks (`/kt-qa <N>` or after every successful process/reprocess)

Run all three QA passes in order. Report results together at the end.

### 1. Set Count + Timecode (automated)

```
! cd ~/Documents/GitHub/kill-tony-archive/backend && uv run python qa_checks.py --episode <N>
```

Runs:
- **Set count check:** expects >= 8 sets. Flag if fewer.
- **Timecode spot-check:** picks a random set, extracts a 15s audio clip at `set_start_seconds`, re-transcribes with Gemini, checks word overlap >= 30%.

Results saved to `data/qa/ep_<N>_qa.json`.

### 2. DB Sanity (SQL spot-check)

```
! sqlite3 ~/Documents/GitHub/kill-tony-archive/data/kill_tony.db "
SELECT
  s.set_number,
  s.comedian_name,
  printf('%d:%02d', CAST(s.set_start_seconds/60 AS INT), CAST(s.set_start_seconds%60 AS INT)) AS start_time,
  s.kill_score,
  s.disclosed_age,
  length(s.set_transcript) AS transcript_chars
FROM sets s
WHERE s.episode_number = <N>
ORDER BY s.set_number;"
```

Flag if:
- Any `comedian_name` is NULL or 'Unknown'
- Any `kill_score` is NULL
- `transcript_chars` < 50 (empty/failed transcription)
- `start_time` values not monotonically increasing
- `disclosed_age` is NULL for a comedian who has appeared before (age backfill may have missed)

### 3. Website Spot-Check (Playwright)

URL: `https://killtonyarchive.com/episodes/<N>`

1. Screenshot the episode page
2. Verify episode number in the title
3. Count visible set cards vs DB set count
4. Check comedian names match
5. If just uploaded, Railway may take ~30s to reflect new data

## QA Report Format

```
QA: Episode #<N>
  ✓ Set count: 12 sets (>= 8 required)
  ✓ Timecode: Set #4 (Comedian Name) at 1:23 — 45% word overlap
  ✓ DB: All sets have names, kill scores, and transcripts
  ✓ Website: 12 sets visible at killtonyarchive.com/episodes/<N>
```

## Upload DB to Railway (`/kt-upload`)

```
! cd ~/Documents/GitHub/kill-tony-archive && just upload-db
```

Requires `RAILWAY_BACKEND_URL` and `ADMIN_SECRET` env vars. The pipeline also auto-syncs after each episode via `sync_db_to_railway()`.

## Environment Requirements

- `.env` at repo root with `GEMINI_API_KEY`
- Modal configured (`modal token set` or `~/.modal.toml`)
- Python deps managed via `uv` (backend/.venv/)
- `yt-dlp`, `ffmpeg` installed
- Playwright available (for website spot-check)
