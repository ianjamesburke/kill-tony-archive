# Kill Tony Data Project — Progress Tracker

## Pipeline Status

The hybrid pipeline (`backend/hybrid_processor.py`) is the canonical processor. It runs 4 passes:

| Pass | Tool | Type | What it does |
|------|------|------|-------------|
| 1 | WhisperX (local) | Audio | Transcription + word-level alignment + speaker diarization (`SPEAKER_00`, etc.) |
| 1.5 | Gemini (cloud) | Text | Maps anonymous `SPEAKER_XX` labels to real names (`tony`, `comedian:name`, etc.) |
| 2 | Gemini (cloud) | Text | Extracts structured set data (name, status, topics, kill score inputs, etc.) |
| 3 | YAMNet (local) | Audio | Laughter/crowd reaction detection — frame-level confidence scores |

Run a full episode end-to-end:
```bash
python3 backend/hybrid_processor.py <episode_number> <youtube_url>
```

Re-run Gemini passes only (uses cached WhisperX output):
```bash
python3 backend/hybrid_processor.py <episode_number> <youtube_url> --skip-whisperx
```

---

## Episode Processing Status

| Episode | In DB | WhisperX cache | Pass 2 JSON | Laughter data | Notes |
|---------|-------|---------------|-------------|---------------|-------|
| 749 | yes | no | no | no | Old batch processor |
| 750 | yes | no | no | no | Old batch processor |
| 751 | yes | no | no | no | Old batch processor |
| 752 | yes | no | no | no | Old batch processor |
| 753 | yes | no | no | no | Old batch processor |
| 754 | yes | yes | yes | yes | First hybrid run, YAMNet crowd data |
| 755 | yes | yes | yes | no | Hybrid pipeline |
| 756 | yes | yes | yes | no | Hybrid pipeline |
| 757 | no | no | no | no | Failed/incomplete |
| 758 | no | yes | no | no | WhisperX done, Gemini passes incomplete |

Episodes 749–753: processed with old all-Gemini pipeline (no WhisperX, no YAMNet). Need reprocessing when backfilling.

---

## Metrics to Manually Verify (per episode)

After a fresh end-to-end run, verify these outputs:

### Regular vs. Bucket Pull
- Every set should be labeled `bucket_pull` or `regular`
- Known regulars: Hans Kim, William Montgomery, David Lucas, Uncle Laser, Kam Patterson, Michael Lair, Ellis Aych, Aron Rhodes, Carlos Suarez, Deadrick Flynn, Ari Matti
- Spot-check: watch 2–3 set intros on YouTube and confirm label matches

### Laughter Hotspots (Pass 3)
- Check `data/crowd_reactions/ep_<N>_crowd_analysis.json` for top laughter windows
- Spot-check: seek to those timestamps in the YouTube video and confirm actual crowd reaction

### Set Timestamps
- Confirm `set_start_seconds` and `set_end_seconds` are reasonable for each set
- Timestamps may drift 1–2 min (known WhisperX issue) but should be in the right ballpark

### Kill Score
- Computed from: `crowd_reaction_score`, `tony_praise_score`, `originality_score`, `performance_score`, `crowd_hype_score`
- `joke_density` was removed (unreliable)
- Verify top-scoring set feels subjectively correct

### Comedian Names
- Check for hallucinations or mislabelings
- Should match the actual lineup for that episode

---

## TODO / Backlog

- [ ] Reprocess episodes 749–753 with hybrid pipeline (currently old-style Gemini-only)
- [ ] Run YAMNet laughter detection on 755, 756 (skipped)
- [ ] WhisperX timestamp drift fix (planned: local alignment tuning or manual correction)
- [ ] Compute `appearance_num` for all comedians from full DB (currently not populated)
- [ ] Frontend: laughter hotspot timeline visualization
- [ ] Frontend: joke topic trend charts over time
- [ ] Frontend: "Best KT minute of all time" generator
- [ ] Backfill historical episodes at scale (1–748)

---

## Known Issues

- `torchcodec` warning on PyTorch 2.8.0 — non-fatal, WhisperX still works (falls back to soundfile)
- `yt-dlp` JS runtime warning — non-fatal, downloads still succeed
- WhisperX timestamps can drift 1–2+ minutes for later parts of long episodes
- YAMNet `.wav` intermediate file is 237MB per episode — clean up after Pass 3 completes
