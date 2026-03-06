# Kill Tony Data Project — Task Tracker

## Completed
- [x] Reprocess ep 751 Pass 2 with improved regular detection prompt
  - Jack Shaw, Deadrick Flynn, Ari Matti all correctly reclassified as regulars
  - Also found a 13th set (Lindsay Campbell) that was previously missed
  - Used gemini-2.5-flash as fallback when 3-flash-preview was 503ing (temp demand issue)

## High Priority

### Reprocess remaining episodes for regular vs bucket_pull accuracy
- Episodes 749, 750, 752, 753 all need Pass 2 re-run with the updated prompt
- The PASS2_PROMPT in batch_processor.py now includes contextual signals:
  - "brand new set from [name]" = regular
  - Set duration > 1 minute = likely regular
  - Tony introducing as regular, closing the show, touring together, etc.
- Can use `reprocess_pass2.py <episode_number>` for each
- No audio re-download needed — cached transcripts exist for all 5 episodes
- Known misclassified sets from DB analysis:
  - Ep 749: Deadrick Flynn (set 7, 3s duration — also has bad timestamps)
  - Ep 750: Dedrick Flynn (set 8, 127s), Remy Swice (set 2, 129s — investigate)
  - Ep 752: JJ Alexander (set 1, 105s), Tony Scar (set 6, 448s), Aaron Belisle (set 15, 123s)
  - Ep 753: Yachao Young (set 1, 122s), Tina La Cochina (set 2, 122s), Fern (set 3, 107s), Dedrick Flynn (set 7, 98s)

### Fix timestamp accuracy (Pass 1 issue)
- Gemini audio transcription timestamps can drift by 1-2+ minutes
- Example: Jack Shaw set listed at 8:02 but actually starts at ~6:02
- This is a Pass 1 problem — Pass 2 only reads what Pass 1 produced
- **Recommended solution: Replace Gemini Pass 1 with local WhisperX**
  - WhisperX gives word-level timestamps via wav2vec2 alignment
  - Free (runs locally), no API rate limits
  - Also includes speaker diarization (could replace our speaker labeling)
  - See: https://github.com/m-bain/whisperX
- Alternative: Timestamp QA pass using small audio windows to validate/correct

## Medium Priority

### Heuristic post-processing layer (planned)
- Point-based scoring system to catch remaining misclassifications
- Signals: set duration, fuzzy name matching across episodes, interview keywords
- Google Search grounding for ambiguous cases (name spelling, regular confirmation)
- Should run after every batch processing as a cleanup step

### Comedian name normalization
- Same person spelled differently across episodes:
  - "Deadrick Flynn" / "Dedrick Flynn" / "Dendrick Flynn"
- Need fuzzy matching + canonical name resolution
- Google Search grounding could help confirm correct spelling

## Model Status (as of March 2026)
- `gemini-3-flash-preview` — active, NOT deprecated, occasional 503s from demand
- `gemini-3-pro-preview` — DEPRECATED March 9, 2026, migrate to 3.1-pro
- `gemini-3.1-flash-lite-preview` — available, free tier (15 RPM, 1000 RPD)
- `gemini-2.5-flash` — stable fallback (10 RPM, 250 RPD free)
- `gemini-2.5-pro` — available on free tier (5 RPM, 100 RPD) — good for Pass 2 only
- No `gemini-3.1-flash` exists yet (they skipped it, went straight to flash-lite)
