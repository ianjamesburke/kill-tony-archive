# Laughter Detection Dev Log

## 2026-03-08: Ground Truth Approach

### Problem
Gemini-based laughter detection (5-second windows, 0-4 scoring) works at scale but accuracy is questionable. We've tried:
- **Event-based timestamps** — Gemini generates start/end times, but timestamps drift on longer audio
- **5-second window scoring** (current production) — Fixed grid eliminates drift, but scoring granularity and accuracy unclear
- **2-second windows** — More resolution, tested on 60min clip
- **YAMNet** — TF Hub audio classifier, 0.48s frames, threshold-based. Already implemented (`yamnet_detect.py`) but blocked by WhisperX timestamp drift for per-set attribution
- **Pro vs Flash** — Tested 2.5 Pro on 60min, marginally better but 50 RPD makes it impractical

### What we don't know
We've never validated any method against human-labeled ground truth. All comparisons have been method-vs-method, not method-vs-reality.

### Plan
1. **Manual labeling tool** (`label_laughter.py`) — Play `test_clip.mp3` (6 min, ep 738), hold SPACE when laughter is heard. Outputs per-second binary timeline to `ground_truth_laughter.json`.

2. **Scoring harness** (`score_laughter_methods.py`) — Runs multiple detection methods on the same clip, compares each to ground truth. Metrics: precision, recall, F1, mean offset.

3. **Methods to test:**

| Method | ID | Description | Cost |
|--------|-----|-------------|------|
| Gemini Flash 5s windows | `gemini_5s` | Current production prompt, 5-second grid | API call |
| Gemini Flash 2s windows | `gemini_2s` | Finer resolution grid | API call |
| Gemini Flash 1s windows | `gemini_1s` | Maximum Gemini resolution | API call |
| Gemini Flash event-based | `gemini_events` | Start/end timestamps per reaction | API call |
| YAMNet (TF Hub) | `yamnet` | Audio classifier, 0.48s frames, threshold 0.15 | Local CPU |
| HuggingFace laughterNet | `hf_laughnet` | `gillesdami/laughter-detection` — CNN trained specifically on laughter | Local CPU/GPU |
| HuggingFace audio classification | `hf_audioclf` | Generic audio classifiers (e.g. `MIT/ast-finetuned-audioset`) with laughter class | Local CPU/GPU |
| Hybrid: YAMNet + Gemini | `hybrid` | YAMNet for timing, Gemini for intensity scaling | Mixed |

### Notes on HuggingFace options

**`gillesdami/laughter-detection`** — Purpose-built laughter detector. CNN-based, outputs frame-level laughter probabilities. Should give much better temporal precision than Gemini since it's an actual audio model running locally. No API costs.

**`MIT/ast-finetuned-audioset`** (Audio Spectrogram Transformer) — Pretrained on AudioSet (same dataset as YAMNet but transformer architecture). Has laughter in its 527 classes. Potentially more accurate than YAMNet's older architecture.

**`facebook/wav2vec2-base`** — Could fine-tune on laughter detection, but that's overkill for now. Worth noting for later.

### Key insight
The local models (YAMNet, HuggingFace) give us sub-second frame-level resolution for FREE (no API calls). They solve the "where is laughter" problem. Gemini's strength is more semantic — it understands context (is the crowd reacting to a joke vs. background noise?). The hybrid approach might be best: local model for timing, Gemini for context/scoring.

### Evaluation metrics
Against ground truth (per-second binary: 0=no laughter, 1=laughter):
- **Precision** — Of seconds the model flagged as laughter, what % actually had laughter?
- **Recall** — Of seconds that had laughter, what % did the model catch?
- **F1** — Harmonic mean of precision/recall
- **Tolerance window** — Allow ±N seconds of slack for timing offset (test at 0s, 1s, 2s, 3s)
- **Active%** — Total % of clip flagged as laughter (sanity check — should be ~15-25% for KT)

---

## 2026-03-09: Ground Truth Results & Production Switch

### Results (6 min test clip, ep 738, ground truth = 78/366s active = 21.3%)

| Method | Prec | Rec | F1 | F1±1s | F1±2s | Active% | Time |
|--------|------|-----|-----|-------|-------|---------|------|
| **gemini_events** | **52%** | **55%** | **54%** | **64%** | **69%** | 22.4% | 19s |
| yamnet_loose (0.05) | 86% | 49% | 62% | 73% | 77% | 12.0% | 6s |
| hybrid_ym_boost | 52% | 77% | 62% | 74% | 79% | 31.7% | 0s |
| hybrid_union | 56% | 64% | 60% | 69% | 73% | 24.6% | 0s |
| gemini_1s | 40% | 51% | 45% | 54% | 62% | 27.3% | 51s |
| hf_ast (5s windows) | 41% | 47% | 44% | 61% | 74% | 24.6% | 116s |
| gemini_5s | 29% | 82% | 43% | 54% | 61% | 60.1% | 35s |
| yamnet (0.15) | 95% | 24% | 39% | 47% | 51% | 5.5% | 8s |
| gemini_2s | 30% | 42% | 35% | 46% | 52% | 30.6% | 41s |

### Key findings
- **gemini_events wins** — best strict F1 (54%), active% closest to truth (22.4% vs 21.3%), fastest Gemini method
- **gemini_5s massively over-flags** (60% active vs 21% truth) — old production had poor precision
- **yamnet is ultra-precise (95%)** but misses most laughter — threshold too conservative
- **All Gemini methods hallucinate in minute 5** (silent section) — only local models stay quiet
- **yamnet_loose** was surprise winner on raw F1 (62%) but low recall (49%)
- **gillesdami/laughter-detection** HF model is removed/private — dead end

### Production changes made
1. **Switched to event-based laughter detection** — prompt asks for start/end timestamps per reaction instead of fixed grid scoring
2. **Chunks reduced from 30min to 15min** — less room for timestamp drift
3. **Pipeline versioning** — `pipeline_version` column added to episodes table (v2 = events-based)
4. **DB as source of truth** — all 489 pending episodes seeded into DB with status/version tracking
5. **Episode titles** stored in DB

### Verified on ep 738
- 10 chunks × 15min, ~45 events per chunk average
- 2260 laughter seconds detected, laughter_pct = 26.2%
- Synced to Railway successfully

---

## 2026-03-09: Batch Processing Setup

### State
- 487 pending, 19 done, 2 error episodes in DB
- Pipeline v2 (events-based laughter) is production-ready
- `cookies.txt` exists but may not work for all age-restricted episodes (Chromium cookie decryption failed on Linux — `no key found` error)
- Episode 743 was stuck in `processing` from an earlier interrupted run, reset to `pending`

### Batch processing moving to Mac
- Linux desktop hit issues with Chromium cookie decryption for age-restricted YouTube episodes
- Batch processing (`python backend/batch_processor.py --limit 50`) will be run from Mac instead
- Command: `python backend/batch_processor.py --limit 50`
- Each episode: download → transcribe (20min chunks) → extract sets (pass 2) → laughter detection (15min chunks) → Railway sync

---

## TODO
- [ ] Export YouTube cookies to `cookies.txt` (Chromium → "Get cookies.txt LOCALLY" extension → youtube.com → export). Needed for age-restricted KT episodes. The batch processor already checks for this file.
- [ ] Re-run laughter detection on all 19 done episodes with `--laughter-only` to upgrade from v1 (5s windows) to v2 (events)
- [ ] Batch process 50 episodes from Mac: `python backend/batch_processor.py --limit 50`

---

## Prior test results (for reference)

### test_clip.mp3 (6 min, ep 738)
- Event-based, 5s windows, 10s windows all tested (`test_laughter_methods.py`)
- Results in `test_laughter_methods_results.json`

### 60min tests (ep 738, first hour)
- Flash 5s: `test_results_60min.json`
- Flash 2s: `test_results_60min_2sec.json`
- Pro 5s: `test_results_pro.json`

### Full episode (ep 738, ~2.4hr)
- Full-file Pro: flatlined after 123 min (output token truncation)
- Chunked Flash (30-min chunks): full coverage, 1726/1726 windows — now in production
