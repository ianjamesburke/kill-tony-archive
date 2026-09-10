---
name: process-backlog
description: Use when the user wants to process the next backlog episode, clear the error queue, or says things like "process the next one", "clear the backlog", "do the next episode", or "process backlogs".
---

# Kill Tony Backlog Processor

Finds the highest-numbered episode in `error` status and runs it through the full pipeline.

## Steps

1. **Find next episode:**
   ```bash
   sqlite3 ~/Documents/GitHub/kill-tony-archive/data/kill_tony.db \
     "SELECT episode_number FROM episodes WHERE status='error' ORDER BY episode_number DESC LIMIT 1;"
   ```
   If no results, check `pending` status. If both empty, tell user the backlog is clear.

2. **Run the pipeline:**
   ```bash
   cd ~/Documents/GitHub/kill-tony-archive && just process <N>
   ```
   Takes 5-10 min. Run in background (`run_in_background: true`).

3. **On success:** Run the DB sanity check and report QA results (set count, timecode, DB spot-check). Ask if they want to upload to Railway.

4. **On failure:**
   - `429` / `RESOURCE_EXHAUSTED` — Gemini rate limit. Wait 60s, retry once. Do NOT loop.
   - `Episode #N not found in database` — should not happen for backlog episodes; investigate.
   - Any other error — report verbatim, don't retry automatically.

## DB Sanity Check (run after every success)

```bash
sqlite3 ~/Documents/GitHub/kill-tony-archive/data/kill_tony.db "
SELECT set_number, comedian_name,
  printf('%d:%02d', CAST(set_start_seconds/60 AS INT), CAST(set_start_seconds%60 AS INT)) AS start_time,
  kill_score, disclosed_age, length(set_transcript) AS transcript_chars
FROM sets WHERE episode_number = <N> ORDER BY set_number;"
```

Flag if: any `comedian_name` NULL, any `kill_score` NULL, `transcript_chars` < 50, timestamps not monotonically increasing.

## QA Report Format

```
QA: Episode #<N>
  ✓/✗ Set count: N sets (>= 8 required)
  ✓/✗ Timecode: Set #X (Name) at M:SS — XX% word overlap
  ✓/✗ DB: All sets have names, kill scores, and transcripts
```
