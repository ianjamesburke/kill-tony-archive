# Kill Tony Data Project — Dev Log

> This file is an AI context document. It records architectural decisions, approach changes, and key findings over the life of the project — so that future AI sessions (and future-you) can understand why things work the way they do without re-reading every file. Consult it before making architectural changes.

---

## 2026-06-02 — [CHANGED] Pass 2 rolling-window chunker replaces single-midpoint split

Old approach: if episode > 90min, split transcript at the midpoint into two halves and call Pass 2 twice. Problem: for a 131min episode the first half was still 68 minutes of transcript — Gemini dropped sets in the middle of the long context (ep 770 lost 5 sets: Max Imum, Nilo Mac, Blix Hanson, Chris Longoria, Sir Winston Pickles).

New approach: always chunk at 40min windows (PASS2_CHUNK_SIZE=2400s) with 5min overlap (PASS2_OVERLAP_SECONDS=300s), stride = 35min. Any episode ≤40min = single call (unchanged). Episodes >40min get N rolling windows, sets deduped by comedian name across windows, sorted by set_start_seconds. Also added gap-detection warning: logs if >20min gap between consecutive sets after extraction.

Also fixed `justfile` reprocess recipe — was passing `--episode N` but reprocess_pass2.py takes a positional arg.

**Breaks if:** episode with >40min of transcript produces fewer sets than expected, or sets are out of order — check for gap warnings in pipeline logs.

## 2026-05-25 — [CHANGED] Pipeline v4: WhisperX on Modal GPU replaces Gemini for Pass 1 transcription

Replaced Gemini audio transcription (Pass 1) with WhisperX large-v3 running on Modal's T4 GPU. Key results from ep_742 benchmarking:
- GPU transcription: 468s (7.8 min) vs local CPU: 9,106s (2.5 hrs) = 19.5x speedup
- Timestamps accurate to ~1s (Gemini drifted 100-700s, root cause of timecode QA failures)
- Cost: ~$0.08/episode on Modal free tier ($30/mo covers ~390 episodes)
- Quality: 90.7% word overlap between GPU and CPU runs (segment boundary differences only)

Pass 2 (Gemini Flash Lite for text extraction) stays as-is. Added WHISPERX_PASS2_PROMPT that handles unlabeled transcripts since WhisperX doesn't identify speakers. Also fixed yt-dlp Chrome cookie issue on macOS (forces TV player, drops audio formats).

Files changed: `backend/batch_processor.py` (PIPELINE_VERSION=4, USE_WHISPERX flag, pass1_whisperx(), WHISPERX_PASS2_PROMPT), `backend/modal_whisperx.py` (new, Modal GPU function).

**Breaks if:** WhisperX segments have no `start` field, Modal GPU times out (>900s), or `modal` package not installed. QA timecode checks should now pass consistently.

## 2026-04-08 — [DECISION] jrgillick/laughter-detection (ResNet) vs Gemini Flash Lite for laughter

Tested the jrgillick/laughter-detection ResNet model (trained on Switchboard corpus) against the current Gemini Flash Lite chunked approach on the same ep_757 chunk. ResNet produced 6 events vs Gemini's 34 for 20 minutes of audio — ResNet is more conservative/precise, Gemini casts a wider net with semantic classification (laughter vs applause vs cheering). ResNet runs fully local (no API cost), but needs several compatibility patches to run on modern Python (see GOTCHA below). Neither approach solves the real blocker: per-set laughter attribution requires accurate WhisperX timestamps first. Keeping Gemini as primary for now; ResNet is a viable local supplement once timestamps are fixed.

## 2026-04-08 — [GOTCHA] jrgillick/laughter-detection requires multiple compat patches for Python 3.11 + modern deps

The library has no PyPI package — clone from GitHub only. The following patches are required to run on Python 3.11 with modern torch/numpy/librosa:
1. `torch.load(..., weights_only=False, map_location='cpu')` — PyTorch 2.6 changed default to weights_only=True; checkpoint uses old format saved on GPU
2. `pip install 'praatio<5'` — praatio 5.x renamed `tgio` → `textgrid`, breaking the import
3. `np.unicode_` removed in NumPy 2.0 — replace with `np.str_` in `audio_utils.py:102`
4. `num_workers=0` in DataLoader — macOS multiprocessing requires `if __name__ == '__main__'` guard which the script lacks
5. librosa positional args removed — `melspectrogram(y, sr, ...)` → `melspectrogram(y=y, sr=sr, ...)` and same for `mfcc()`
6. Default stride=1 in `SwitchBoardLaughterInferenceDataset` means 51,500 windows for 20min audio (~20min on CPU). Added `stride` param; stride=5 gives ~10,300 windows and finishes in ~4min with no meaningful quality loss for laughter segmentation.

## 2026-04-08 — [GOTCHA] yt-dlp with Chrome cookies forces TV player, drops audio formats

Passing `cookiesfrombrowser: ("chrome",)` to yt-dlp causes it to use the "tv downgraded player" API path instead of the standard "android vr + web safari" path. The TV player doesn't offer audio-only formats (140/251), so `bestaudio/best` raises "Requested format is not available." Fix: don't use Chrome cookies on macOS — let yt-dlp use the standard player path. The existing `_yt_cookie_opts()` flow is correct; the issue only surfaced when testing manually with `--cookies-from-browser chrome`.

## 2026-04-08 — [GOTCHA] yt-dlp JS challenge solver (deno) version mismatch breaks audio download

The cached deno challenge solver script was v0.5.0 but yt-dlp 2026.3.17 requires v0.8.0. Without a valid solver, the n-challenge fails and audio format URLs get throttled/dropped. Fix: add `"remote_components": {"ejs:github"}` to `_yt_base_opts()` — this auto-fetches the latest solver from GitHub on first use and caches it. One-time internet hit, then works offline.

## 2026-04-08 — [GOTCHA] Broken venv from renamed project directory
The `.venv` at `backend/.venv` was created when the repo lived at `kill-tony-data-project-v1/`. After the repo was moved/renamed, all venv shebang lines still pointed at the old path, making pip and python unusable. Fix: `rm -rf backend/.venv && python3 -m venv backend/.venv && .venv/bin/pip install -r requirements-pipeline.txt`. If venv breaks again after a repo move, this is why.

## 2026-03-28 — SEO shipped, Google Search Console live, og:image, r/KillTony strategy

### SEO PR (seo-improvements branch → main)
- **PR #2** created, reviewed by Claude Code, all issues addressed:
  - Added `og:image` meta tags (YouTube thumbnails for episode pages, default fallback for everything else)
  - Fixed `twitter:card` — default `summary`, upgrades to `summary_large_image` on episode pages with video
  - Removed unused `today` variable in sitemap.xml generator
  - Fixed mid-word truncation in meta descriptions (word-boundary-aware `.slice(0,155).replace(/\s+\S*$/, '') + '...'`)
  - Fixed empty string episode_summary passing truthy check (now uses `.trim()`)
- Merged to main, deployed to Railway

### og:image
- Generated 5 design options via HTML→screenshot pipeline
- Selected option 5: dark editorial with spotlight gradient, red "Archive" badge, stats (510+ episodes, 835+ sets, 593+ comedians)
- Lives at `frontend/static/og-default.png`, served at `https://killtonyarchive.com/og-default.png`

### Google Search Console
- Verified via meta tag method (`google-site-verification` in `+layout.svelte`)
- Sitemap submitted: `https://killtonyarchive.com/sitemap.xml`
- Only homepage indexed so far — full crawl will take days

### Railway Deploy
- Frontend and backend services now linked via Railway CLI on Linux (both dirs independently linked)
- Deploy: `cd frontend && railway up --detach` / `cd backend && railway up --detach`

### r/KillTony Posting Strategy
- Confirmed: new episodes drop every Monday night, subreddit peaks Tuesday/Wednesday
- Calendar reminder set for Tuesday 7am to post archive link during peak activity

---

## 2026-03-28 — Pipeline fixes: model fallback, error tracking, QA checks

### Problem
Pipeline had been stuck for 4 days. Episode #761 (Houston — Adam Ray + Kim Congdon) failed repeatedly on chunk 4/9 — `gemini-3.1-flash-lite-preview` returned malformed JSON (no parseable array) every attempt. Since `daily_processor.py` always picks the newest error/pending episode, ep 761 blocked all progress. Additionally, 11 episodes were stuck in "processing" status from systemd timeout kills, and the deno JS challenge solver for yt-dlp was erroring (non-fatal since audio was cached).

### Root cause
`gemini-3.1-flash-lite-preview` is unreliable at returning structured JSON for certain audio chunks — specifically chunk 4 (offset 51:00) of ep 761 failed 100% of the time across dozens of attempts over 4 days. The lite model seems to choke on certain audio segments (possibly noisy crowd sections or music transitions).

### Fixes

**1. Model fallback system** (`batch_processor.py`)
- Primary: `gemini-3.1-flash-lite-preview` (4 attempts)
- Fallback: `gemini-3-flash-preview` (3 attempts)
- Flash-lite is preferred for rate limits (1000 RPD vs 250 RPD), but when it fails to return valid JSON, the stronger flash model takes over. Ep 761 chunk 4 succeeded on the first flash attempt.
- Note: `gemini-3.1-flash-preview` does NOT exist as a model name. The correct 3.x flash model is `gemini-3-flash-preview`. This was discovered the hard way (404 errors).

**2. Error count tracking** (`batch_processor.py` + DB schema)
- Added `error_count` and `last_error` columns to episodes table
- `update_episode_status()` increments `error_count` on errors, resets to 0 on success
- `daily_processor.py` skips episodes with 3+ consecutive failures — prevents infinite death loops
- Skipped episodes retry automatically when pipeline version bumps

**3. Stuck episode recovery**
- Reset 11 "processing" episodes back to "pending" (killed mid-run by systemd timeout)
- Increased systemd `TimeoutStartSec` from 3600s to 5400s (90 min) to accommodate retry loops

**4. QA checks** (`backend/qa_checks.py`)
Two post-processing checks now run after every episode, before audio cleanup:

- **Set count validation**: Flags episodes with < 8 sets. Most KT episodes have 9-15 bucket pulls + regulars. Below 8 means Pass 2 likely missed sets. Initial scan: 6/70 done episodes flagged (705, 707, 713, 724, 726, 761).
- **Timecode spot-check**: Randomly picks a set, extracts 15s of audio at `set_start_seconds` via ffmpeg, transcribes via Gemini, compares word overlap with stored transcript. Catches misaligned timecodes where the set starts at the wrong point in the video.

Results saved to `data/qa/ep_*_qa.json`. Standalone CLI: `python3 qa_checks.py --all --set-count-only` or `--episode 761`.

**5. Heartbeat monitoring**
Added Kill Tony pipeline health check to heartbeat (every 4 hours):
- Checks systemd service status and recent journal output
- Queries DB for processing progress
- Auto-resets stuck "processing" episodes
- Alerts if no progress in 24 hours

### Available Gemini models (as of 2026-03-28)
For reference, the valid model names on the free tier:
- `gemini-3.1-flash-lite-preview` — cheapest, 1000 RPD, unreliable on some audio chunks
- `gemini-3-flash-preview` — mid-tier, better JSON reliability
- `gemini-3.1-pro-preview` — most capable, lowest rate limits
- `gemini-2.5-flash` — previous gen, still available

### State after fixes
- 70 episodes done (was 69), 422 pending, 15 errors, 2 skipped
- Timer running 3x daily (10am, 12pm, 2pm MT)
- Episode #761 successfully processed: 5 sets extracted (flagged by QA — needs Pass 2 re-run for missing sets)

---

## 2026-03-09 — Railway deployment: GitHub CI, RAILPACK, monorepo config

Re-linked both services to GitHub (`ianjamesburke/kill-tony-archive`) after repo refactor disconnected them. Configured as an isolated monorepo with `rootDirectory` per service (`/backend`, `/frontend`). Key changes:

- **Builder**: Migrated from NIXPACKS (deprecated) to RAILPACK for both services
- **Watch patterns**: `backend/**` and `frontend/**` — prevents cross-service redeploys on unrelated changes
- **Auto-deploy**: Push to `main` triggers deploy for affected services only
- **Node version**: Replaced `NIXPACKS_NODE_VERSION` env var with `RAILPACK_NODE_VERSION=24`
- **No config files**: All deployment config lives in Railway service settings (via CLI/API), not in-repo `railway.json` files — cleaner, no drift between config file and dashboard

---

## 2026-03-09 — Split models for pipeline, daily processor cron job

Split the single `MODEL` constant into `PASS1_MODEL` (gemini-2.5-flash) and `PASS2_MODEL` (gemini-3.1-flash-lite-preview). Testing showed 2.5-flash produces 4x more granular transcripts for Pass 1 (audio), while flash-lite is adequate for Pass 2 (text-only set extraction) and laughter detection. This avoids burning all the 2.5-flash free tier quota (250 RPD) on cheap text tasks that flash-lite (1000 RPD) handles fine.

Added `daily_processor.py` — a standalone script that processes one episode per run. Checks the Kill Tony YouTube channel for new episodes first; if none found, backfills the oldest unprocessed episode from the DB. Designed to be triggered by cron or systemd timer on Linux. Includes systemd unit files in `backend/cron/`.

---

## 2026-03-09 — Sets page pagination, time filters, /api/sets/stats endpoint

Sets page was loading 200 sets at once and rendering all of them — slow initial load and gets worse as the DB grows. Switched to 50/page with client-side fetch (same fade pattern as homepage Top Sets). Added time period filter tabs (All Time / Last Year / Last 30 Days / Last Episode) to the sets page.

Added `/api/sets/stats` endpoint (`get_sets_stats()` in database.py) that returns scores array, crowd reactions, bucket/regular counts and averages filtered by time period. The stats endpoint drives the histogram and status breakdown cards — decoupled from the paginated list so stats always reflect the full period, not just the current page.

Also added `idx_sets_kill_score` index on `sets(kill_score)` — free win for ORDER BY queries.

Status filter is now server-side (triggers a re-fetch). Search is still client-side (filters current page only) — acceptable for now, revisit if users complain.

---

## 2025 (early) — Initial pipeline exploration

Single-pass transcription + analysis attempted (one Gemini call to transcribe audio and extract set data simultaneously). Results were too sparse — Gemini returned only ~14 entries for a 90min episode and missed most sets entirely. Abandoned in favor of a two-pass approach.

---

## 2025 — Two-pass chunked pipeline established

**What:** Split pipeline into Pass 1 (audio → speaker-labeled transcript) and Pass 2 (transcript text → structured set data).

**Why:** Single-pass gave terrible results. Keeping transcription separate from analysis lets each prompt be focused, and caching the transcript means Pass 2 can be re-run cheaply without re-uploading audio.

**Chunking added:** 20-minute chunks with 3-minute overlap. Without chunking, Gemini hits its output token limit ~53 minutes into a 90-minute episode, silently dropping the rest. 3 minutes of overlap is sufficient — a full set + transition is never longer than ~2 minutes.

---

## 2025 — Model selection: Flash vs Flash Lite

Flash Lite returned ~16 transcript entries per 30-minute chunk. Flash 3 returned 200+. Flash Lite was too sparse for reliable set detection. Settled on `gemini-3-flash-preview` for Pass 1.

---

## 2025 — Removed: joke_count, joke_density

Gemini's joke counts were subjective and inconsistent. `joke_density` (jokes per minute) was derived from these counts combined with WhisperX timestamps, which themselves drift 1–2+ minutes. The compound unreliability made the field misleading. Removed both from extraction.

---

## 2025 — Removed: appearance_num from Pass 2 extraction

Gemini was hallucinating appearance numbers. Now computed from the full database after all episodes are processed.

---

## 2025 — Merged: first_timer into bucket_pull

The distinction between a first-timer and a bucket pull is meaningless at extraction time — it can be computed later from appearance count. Simplified to a single `bucket_pull` boolean.

---

## 2025 — Removed: inferred demographics and disclosed fields

Fields like `inferred_gender`, `inferred_ethnicity`, `inferred_age`, `disclosed_has_kids`, `self_disclosed_extra`, `guest_feedback_sentiment` were either unreliable extractions or unused downstream. Removed to keep the schema clean.

---

## 2025 — Regular vs bucket pull detection improved

Hardcoded regulars list was insufficient — new regulars get added over time and the list becomes stale. Added contextual signals to the Pass 2 prompt: phrasing like "a brand new set from [name]", set duration > ~90s, Tony introducing as a regular, touring together, etc. This makes detection more robust without needing to maintain a static list.

---

## 2026-03-06 — Time period filters, YouTube timestamp autoplay, homepage cleanup

Added time period filters (All Time / This Year / Last 6 Months) to the Top Sets page. Fixed YouTube embed autoplay via `start=` parameter in URL. Minor homepage layout cleanup.

---

## 2026-03-08/09 — Laughter detection research & production switch

Explored multiple laughter detection approaches and benchmarked them against a 6-minute hand-labeled ground truth clip (ep 738, 21.3% laughter).

**Methods tested:** Gemini event-based, Gemini 5s/2s/1s windows, YAMNet (TF Hub, 0.48s frames), HuggingFace AST, hybrid combinations.

**Results summary:**

| Method | F1 | F1±1s | Active% |
|--------|-----|-------|---------|
| gemini_events | 54% | 64% | 22.4% |
| yamnet_loose (0.05) | 62% | 73% | 12.0% |
| hybrid_ym_boost | 62% | 74% | 31.7% |
| gemini_5s (old prod) | 43% | 54% | 60.1% |

**Key findings:**
- `gemini_5s` (old production) massively over-flagged — 60% active vs 21% truth, poor precision
- `gemini_events` won on strict F1 and closest active% to ground truth — best overall
- YAMNet ultra-precise (95%) but low recall (24%) at default threshold 0.15; loosening to 0.05 improves recall but still misses edge cases
- All Gemini methods hallucinate laughter in a silent section at minute 5; local models stay quiet
- `gillesdami/laughter-detection` HuggingFace model is private/removed — dead end

**Production changes made:**
- Switched to event-based laughter detection (start/end timestamps per reaction, not fixed grid)
- Chunks reduced 30min → 15min to reduce timestamp drift
- Added `pipeline_version` column to episodes table (v2 = events-based)
- Seeded all 489 pending episodes into DB with status/version tracking

**Still blocked:** Per-set laughter attribution requires accurate set boundary timestamps. WhisperX timestamp drift (1–2+ min) causes misattribution. Revisit once WhisperX is integrated for Pass 1.

---
