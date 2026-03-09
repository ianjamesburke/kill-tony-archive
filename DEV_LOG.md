# Kill Tony Data Project — Dev Log

> This file is an AI context document. It records architectural decisions, approach changes, and key findings over the life of the project — so that future AI sessions (and future-you) can understand why things work the way they do without re-reading every file. Consult it before making architectural changes.

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
