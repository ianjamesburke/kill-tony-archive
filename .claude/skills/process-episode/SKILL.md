---
name: process-episode
description: "Process Kill Tony episodes through the full pipeline (download → transcribe → extract → SQLite) and run post-processing QA checks including website spot-verification."
risk: low
source: local
---

# Kill Tony Episode Processor

Process one or more Kill Tony episodes through the full pipeline using the local justfile commands. Includes post-processing QA: set count check, timecode spot-checks, and live website verification.

## Trigger

Use this skill when the user says:
- `/process-episode <N>` — process a specific episode
- `/reprocess-episode <N>` — re-run Pass 2 only (uses cached transcript)
- `/kt-qa <N>` — run QA checks only (no pipeline rerun)
- `/kt-status` — show pipeline status across all episodes
- `/kt-upload` — upload local DB to Railway
- Anything like "process episode 742", "run the pipeline for 758", "reprocess 730", "check episode 758"

## Working Directory

All commands must run from `~/Documents/GitHub/kill-tony-archive/`. The justfile lives there.

## Commands Reference

```bash
just process 742       # Full pipeline: download → Pass 1 → Pass 2 → SQLite (includes QA)
just reprocess 742     # Pass 2 only (requires cached audio from a prior run)
just qa 742            # QA checks only: set count + timecode spot-checks
just batch 5           # Process up to 5 pending episodes
just upload-db         # Upload local SQLite to Railway (requires ADMIN_SECRET env var)

# Direct script calls:
cd backend && .venv/bin/python batch_processor.py --status     # Show all episode statuses
cd backend && .venv/bin/python qa_checks.py --episode 742      # Standalone QA run
```

## Process Episode (`/process-episode <N>`)

1. **Check status first:**
   ```
   ! cd ~/Documents/GitHub/kill-tony-archive/backend && .venv/bin/python batch_processor.py --status 2>/dev/null | grep -E "^\S+ +<N>"
   ```
   If already `done`, confirm with user before reprocessing (suggest `/reprocess-episode <N>` for Pass 2 only).

2. **Run the pipeline:**
   ```
   ! cd ~/Documents/GitHub/kill-tony-archive && just process <N>
   ```
   This takes 5–20 minutes. The script logs progress to stdout. QA checks (set count + timecode) run automatically at the end via `qa_checks.py`.

3. **On success:** Immediately run the full QA suite (see QA Checks section below), then ask if they want to upload to Railway (`just upload-db`).

4. **On failure — handle common errors:**
   - `429 Resource Exhausted` / `RESOURCE_EXHAUSTED` — Gemini rate limit. Tell user to wait 60s and retry. Do NOT retry automatically in a loop.
   - `yt-dlp` download failure — YouTube may have blocked or changed the video ID. Check the episode URL in the DB.
   - `Episode #N not found in database` — add it to `data/episodes.json` first.
   - Any other error — show the last 20 lines of output and ask how to proceed.

## Reprocess Episode (`/reprocess-episode <N>`)

Runs Pass 2 only. Useful when Pass 2 extraction failed or the prompt was updated.

```
! cd ~/Documents/GitHub/kill-tony-archive && just reprocess <N>
```

Requires cached audio at `backend/audio_cache/ep_<N>/full.mp3`. If missing, run the full pipeline instead.

After reprocess completes, run QA checks (see below).

## QA Checks (`/kt-qa <N>` or after every successful process/reprocess)

Run all three QA passes in order. Report results together at the end.

### 1. Set Count + Timecode (automated)

```
! cd ~/Documents/GitHub/kill-tony-archive/backend && .venv/bin/python qa_checks.py --episode <N>
```

This runs:
- **Set count check:** expects ≥ 8 sets. Flag if fewer.
- **Timecode spot-check:** picks a random set, extracts a 15s audio clip at `set_start_seconds`, re-transcribes with Gemini, checks word overlap ≥ 30%.

Results are also saved to `data/qa/ep_<N>_qa.json`.

### 2. DB Sanity (SQL spot-check)

Run this query and show the results to the user:
```
! sqlite3 ~/Documents/GitHub/kill-tony-archive/data/kill_tony.db "
SELECT
  s.set_number,
  s.comedian_name,
  printf('%d:%02d', CAST(s.set_start_seconds/60 AS INT), CAST(s.set_start_seconds%60 AS INT)) AS start_time,
  s.kill_score,
  length(s.set_transcript) AS transcript_chars
FROM sets s
WHERE s.episode_number = <N>
ORDER BY s.set_number;"
```

Flag if:
- Any row has `comedian_name` = NULL or 'Unknown'
- Any row has `kill_score` = NULL (Pass 2 extraction incomplete)
- `transcript_chars` < 50 for any set (likely empty/failed transcription)
- `start_time` values are not monotonically increasing (timecode ordering issue)

### 3. Website Spot-Check (Playwright)

Use headless Playwright to screenshot the live episode page and verify it matches the DB.

URL: `https://killtonyarchive.com/episodes/<N>`

Steps:
1. Take a screenshot of the full episode page
2. Verify the episode number in the page title matches `<N>`
3. Count the visible set cards on screen — compare against the DB set count from step 1
4. Check that at least one comedian name visible on the page matches a name from the DB query above
5. If the episode was just uploaded, warn that Railway may take ~30s to reflect the new data — suggest waiting and retrying if counts don't match

Report: "Website shows N sets, DB has M sets — [MATCH / MISMATCH]"

If there's a mismatch: most likely the DB hasn't been uploaded to Railway yet. Prompt: "Run `just upload-db` and then re-check."

## QA Report Format

After all checks, output a summary like:
```
QA: Episode #<N>
  ✓ Set count: 12 sets (≥ 8 required)
  ✓ Timecode: Set #4 (Comedian Name) at 1:23 — 45% word overlap
  ✓ DB: All sets have names, kill scores, and transcripts
  ✓ Website: 12 sets visible at killtonyarchive.com/episodes/<N>
```

Or for failures:
```
  ✗ Set count: 5 sets — LOW (suggest rerun Pass 2 with `just reprocess <N>`)
  ✗ Timecode: Set #7 at 2:11 — 12% overlap (mismatch — transcript may be misaligned)
  ✗ Website: 0 sets visible — DB not uploaded yet, run `just upload-db`
```

## Pipeline Status (`/kt-status`)

```
! cd ~/Documents/GitHub/kill-tony-archive/backend && .venv/bin/python batch_processor.py --status
```

Summarize: total done, total pending, any errors.

## Upload DB to Railway (`/kt-upload`)

```
! cd ~/Documents/GitHub/kill-tony-archive && just upload-db
```

Requires `ADMIN_SECRET` env var. If it fails with "Set ADMIN_SECRET", tell user:
```
export ADMIN_SECRET=<value from Railway dashboard>
```

## Batch Processing

```
! cd ~/Documents/GitHub/kill-tony-archive && just batch <LIMIT>
```

Default limit is 5. After batch completes, run QA on each processed episode.

## Environment Requirements

- `.env` at repo root with `GEMINI_API_KEY`
- Python venv at `backend/.venv/`
- `yt-dlp`, `ffmpeg` installed
- `deno` at `~/.deno/bin/` (handled automatically by the script)
- Playwright available (for website spot-check step)
