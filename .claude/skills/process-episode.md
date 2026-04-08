# Kill Tony Episode Processor

Process one or more Kill Tony episodes through the full pipeline using the local justfile commands.

## Trigger

Use this skill when the user says:
- `/process-episode <N>` — process a specific episode
- `/reprocess-episode <N>` — re-run Pass 2 only (uses cached transcript)
- `/kt-status` — show pipeline status across all episodes
- `/kt-upload` — upload local DB to Railway
- Anything like "process episode 742", "run the pipeline for 758", "reprocess 730"

## Working Directory

All commands must run from `~/Documents/GitHub/kill-tony-archive/`. The justfile lives there.

## Commands Reference

```bash
just process 742       # Full pipeline: download → Pass 1 → Pass 2 → SQLite
just reprocess 742     # Pass 2 only (requires cached audio from a prior run)
just batch 5           # Process up to 5 pending episodes
just upload-db         # Upload local SQLite to Railway (requires ADMIN_SECRET env var)

# Direct script calls (for flags not in justfile):
cd backend && .venv/bin/python batch_processor.py --status          # Show all episode statuses
cd backend && .venv/bin/python batch_processor.py --laughter-only --episode 742  # Laughter detection only
```

## Process Episode (`/process-episode <N>`)

1. **Check status first.** Run:
   ```
   ! cd ~/Documents/GitHub/kill-tony-archive/backend && .venv/bin/python batch_processor.py --status 2>/dev/null | grep -E "^[✓✗ ] +<N>"
   ```
   If already `done`, confirm with user before reprocessing (suggest `/reprocess-episode <N>` for Pass 2 only).

2. **Run the pipeline:**
   ```
   ! cd ~/Documents/GitHub/kill-tony-archive && just process <N>
   ```
   This can take 5–20 minutes depending on episode length. The script logs progress to stdout.

3. **On success:** Confirm the episode is now `done` in the DB. Ask if they want to upload to Railway now (`just upload-db`).

4. **On failure — handle common errors:**
   - `429 Resource Exhausted` / `RESOURCE_EXHAUSTED` — Gemini rate limit hit. Tell user to wait 60s and retry. Do NOT retry automatically in a loop.
   - `yt-dlp` download failure — YouTube may have blocked or changed the video ID. Check the episode entry in the DB for the URL.
   - `Episode #N not found in database` — the episode isn't in the episodes JSON yet. Tell user to add it to `data/episodes.json` first.
   - Any other error — show the last 20 lines of output and ask how to proceed.

## Reprocess Episode (`/reprocess-episode <N>`)

Runs Pass 2 only. Useful when Pass 2 extraction failed or the prompt was updated.

```
! cd ~/Documents/GitHub/kill-tony-archive && just reprocess <N>
```

Requires cached audio at `backend/audio_cache/ep_<N>/full.mp3`. If missing, tell user to run the full pipeline instead.

## Pipeline Status (`/kt-status`)

```
! cd ~/Documents/GitHub/kill-tony-archive/backend && .venv/bin/python batch_processor.py --status
```

Show the output. Summarize: total done, total pending, any errors.

## Upload DB to Railway (`/kt-upload`)

```
! cd ~/Documents/GitHub/kill-tony-archive && just upload-db
```

Requires `ADMIN_SECRET` env var. If it fails with "Set ADMIN_SECRET", tell user to set it:
```
export ADMIN_SECRET=<value from Railway dashboard>
```

## Batch Processing

If user wants to process multiple episodes at once:
```
! cd ~/Documents/GitHub/kill-tony-archive && just batch <LIMIT>
```

Default limit is 5. Processes oldest pending episodes first.

## Environment Requirements

- `.env` file at repo root with `GEMINI_API_KEY`
- Python venv at `backend/.venv/`
- `yt-dlp`, `ffmpeg` installed (in PATH or via brew)
- `deno` at `~/.deno/bin/` (for yt-dlp JS challenge solving — already handled by the script)

If any are missing, diagnose before running and tell user what to install.
