# Next Steps — Batch Processing Test Run

## Goal
Process 10 episodes end-to-end, store results in SQLite, validate data quality.

## Step 1: Build the Batch Processor
Convert `test_two_pass.py` into a production batch script that:
- Takes a list of YouTube URLs or episode numbers
- Processes one episode at a time
- Respects Gemini free tier rate limits (30s delay between API calls)
- Saves all data to SQLite after each episode (resume-safe)
- Pulls YouTube stats (views, likes, comments) from yt-dlp metadata
- Adds inferred demographics to pass 2 prompt
- Replaces `walked_off` with `cut_short` in prompts
- Normalizes speaker labels in post-processing (merge variants like `uncle_laser`/`uncle_lazer`)
- Computes `laugh_count` per episode from pass 1 transcript
- Computes `kill_score` per set after extraction
- Logs progress and errors

## Step 2: Set Up SQLite Schema
Create tables matching SCHEMA.md:
- `episodes` — episode-level data + YouTube stats
- `sets` — one row per comedian set
- `transcript_entries` — full speaker-labeled transcript
- Indexes on episode_number, comedian_name

## Step 3: Test Run — 10 Episodes
Pick 10 episodes with variety:
- Mix of well-known guests and lesser-known
- Mix of eras (early, middle, recent)
- At least one with a golden ticket moment
- At least one with Hans Kim, William Montgomery, David Lucas

Estimate: ~7 API calls per episode × 10 episodes = 70 calls.
At 30s per call = ~35 minutes total processing time.
Well within free tier daily limit of 1,500 requests.

## Step 4: Validate
After processing, spot-check:
- Are all sets captured? (compare to known episode recaps online)
- Are regulars correctly labeled?
- Do kill scores feel right? (sort by score, check top/bottom)
- Are YouTube stats populated?
- Do demographics only appear when explicitly mentioned?

## Step 5: Compute Derived Fields
After batch completes:
- Calculate `appearance_num` per comedian across all episodes
- Verify `kill_score` distribution has good spread
- Calculate `laugh_count` per episode

## After Test Run
- Fix any prompt issues found during validation
- Scale up: process remaining 600+ episodes over ~3 days
- Begin frontend development

---

## Domain Options

**Already Taken:**
- `killtonystats.com` — active site
- `killtonydb.com` — active "Complete Kill Tony Database"

**Candidates to Check:**
- `killtonyarchives.com` — check [Namecheap](https://www.namecheap.com/domains/domain-name-search/) or [GoDaddy](https://www.godaddy.com/domains)
- `killtonydata.com`
- `killtonyanalytics.com`
- `tonydatabase.com`

Most `.com` domains are $8-15/year first year, often cheaper renewal after year 1.
