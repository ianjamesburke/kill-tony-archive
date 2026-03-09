# Kill Tony Archive

**[killtonyarchive.com](https://killtonyarchive.com)**

A data science project that transcribes, analyzes, and ranks every 1-minute stand-up set from the Kill Tony podcast — and uses that data to answer the question: *what is the best Kill Tony minute of all time?*

---

## What is Kill Tony?

[Kill Tony](https://www.youtube.com/@KillTony) is a weekly stand-up comedy podcast hosted by Tony Hinchcliffe. Random comedians pull a golden ticket from a bucket and get exactly one minute on stage. After the set, Tony interviews them live. The show has run for 700+ episodes with some of the biggest names in comedy as guests.

It's one of the most unique formats in stand-up — raw, unfiltered, and ruthlessly honest. A lot of careers have started (and ended) on that stage.

---

## What This Project Does

Every episode gets run through a two-pass AI pipeline:

1. **Pass 1 — Transcription:** Episode audio is downloaded and fed to Gemini in overlapping 20-minute chunks. Each chunk comes back as a speaker-labeled transcript (`tony`, `comedian:hans_kim`, `crowd`, etc.)

2. **Pass 2 — Analysis:** The merged transcript text is sent back to Gemini for structured data extraction: comedian name, set transcript, topic tags, crowd reaction, Tony's praise level, whether they got a golden ticket, interview summary, and more.

3. **Kill Score:** Each set gets scored based on crowd reaction, Tony's praise, joke book size, and bonus events (golden ticket, secret show invite, told to sign up again).

4. **Frontend:** A SvelteKit dashboard at [killtonyarchive.com](https://killtonyarchive.com) surfaces the data — top sets, topic trends over time, guest appearances, episode pulse charts, and a side-by-side voting system.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Pipeline | Python, Google Gemini API (audio + text), yt-dlp, ffmpeg |
| Backend | FastAPI, SQLite |
| Frontend | SvelteKit, TypeScript |
| Hosting | Railway |

---

## Architecture

```
YouTube URL
    │
    ▼
yt-dlp → MP3
    │
    ▼
Split into 20min chunks (3min overlap)
    │
    ▼
Pass 1: Gemini Audio → Speaker-labeled transcript JSON
    │
    ▼
Merge chunks, deduplicate overlaps, normalize speaker labels
    │
    ▼
Pass 2: Gemini Text → Structured set data (JSON)
    │
    ▼
SQLite → FastAPI → SvelteKit
```

The two-pass design was deliberate — single-pass (transcribe + analyze together) produced sparse, low-quality results. Separating concerns gave 10x more transcript entries per episode and dramatically better set extraction accuracy.

---

## Kill Score Formula

```
kill_score = (tony_praise_level × 2)    # 2–10 pts
           + crowd_reaction_score        # 0–4 pts (silence → roaring)
           + joke_book_score             # 0–3 pts (none → large)
           + golden_ticket × 10          # bonus
           + secret_show_invite × 5      # bonus
           + sign_up_again × 2           # bonus
```

Theoretical max: 29. Used to rank every set in the database.

---

## Project Structure

```
backend/
  batch_processor.py    # Main pipeline (download → Pass 1 → Pass 2 → SQLite)
  reprocess_pass2.py    # Re-run Pass 2 only (uses cached transcript)
  daily_processor.py    # Incremental episode processor for scheduled runs
  main.py               # FastAPI server + REST endpoints
  database.py           # SQLite schema, CRUD, kill score computation
  episodes.json         # Episode list with processing status

frontend/
  src/routes/           # SvelteKit pages (overview, episodes, sets, guests, vote)
  src/lib/api.ts        # API client

data/
  transcripts/          # Cached Pass 1 transcript JSON (gitignored)

scripts/
  sync-db-to-railway.sh # Upload local DB to production
```

---

## Key Design Decisions

A running log of architectural decisions and why they were made is in [DEV_LOG.md](DEV_LOG.md).

Some highlights:
- **Two-pass pipeline** instead of single-pass — single-pass outputs were too sparse to be useful
- **Chunked audio** (20min + 3min overlap) — Gemini hits output token limits on full-length episodes (~90min), silently dropping the last 30+ minutes
- **`appearance_num` not extracted by AI** — Gemini hallucinated these values; now computed from the full DB
- **`joke_density` removed from kill score** — too noisy; Gemini joke counts are subjective and timestamp drift affects set window accuracy

---

## Data Notes

- Transcription timestamps from Gemini can drift 1–2 minutes from actual audio position (a known limitation of LLM audio transcription)
- The planned fix is replacing Pass 1 with local [WhisperX](https://github.com/m-bain/whisperX) for word-level timestamps
- Sentiment/demographic fields were explored and removed — unreliable at scale

---

## Roadmap

See [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) for the full list. Top candidates:
- WhisperX for accurate timestamps → enables laughter attribution per set
- Joke-level segmentation (score individual jokes, not just full sets)
- Comedy DNA clustering (k-means on topic tags to group comedians by style)
- Survival analysis (what % of bucket pulls ever return?)
- YouTube comment sentiment vs AI kill scores

---

## Contributing

This started as a portfolio project but the data is genuinely interesting. If you're a Kill Tony fan and want to contribute — better prompts, additional episode coverage, new visualizations — PRs are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

---

## License

MIT
