"""
Score laughter detection methods against human-labeled ground truth.

Usage:
    python scripts/score_laughter_methods.py                    # run all methods
    python scripts/score_laughter_methods.py --methods gemini_5s yamnet  # run specific methods
    python scripts/score_laughter_methods.py --score-only       # just score cached results

Requires: ground_truth_laughter.json (from label_laughter.py)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

AUDIO_PATH = Path(__file__).parent / "test_clip.mp3"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth_laughter.json"
RESULTS_PATH = Path(__file__).parent / "scored_results.json"
DURATION = 366


# ─── Scoring ────────────────────────────────────────────────────────────────

def score_timeline(predicted: list[int], ground_truth: list[int], tolerance: int = 0) -> dict:
    """Score a per-second predicted timeline against ground truth.

    tolerance: allow ±N seconds of slack. If any ground truth second within
    ±tolerance is 1, a predicted 1 at that position counts as a true positive.
    """
    length = min(len(predicted), len(ground_truth))
    tp = fp = fn = tn = 0

    for i in range(length):
        pred = 1 if predicted[i] > 0 else 0
        # With tolerance, check if ANY nearby ground truth second is positive
        if tolerance > 0:
            nearby_true = any(
                ground_truth[j] > 0
                for j in range(max(0, i - tolerance), min(length, i + tolerance + 1))
            )
            nearby_pred = any(
                predicted[j] > 0
                for j in range(max(0, i - tolerance), min(length, i + tolerance + 1))
            )
        else:
            nearby_true = ground_truth[i] > 0
            nearby_pred = pred > 0

        actual = 1 if ground_truth[i] > 0 else 0

        if pred and nearby_true:
            tp += 1
        elif pred and not nearby_true:
            fp += 1
        elif not pred and actual and not nearby_pred:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    active_pred = sum(1 for s in predicted[:length] if s > 0)
    active_truth = sum(1 for s in ground_truth[:length] if s > 0)

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "active_pred_pct": round(active_pred / length * 100, 1),
        "active_truth_pct": round(active_truth / length * 100, 1),
    }


# ─── Method: Gemini window-based ────────────────────────────────────────────

def run_gemini_windows(window_size: int) -> list[int]:
    """Run Gemini Flash with fixed-window scoring."""
    from google import genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    num_windows = DURATION // window_size

    prompt = f"""
Listen to this audio clip from a Kill Tony comedy show. Your job is to detect CROWD REACTIONS ONLY.

The audio is {DURATION} seconds long ({DURATION // 60} minutes). Divide it into {num_windows} consecutive {window_size}-second windows.

For each window, score the CROWD LAUGHTER/APPLAUSE level. Return a JSON array:

[
  {{"w": 0, "s": 0}},
  {{"w": 1, "s": 0}},
  {{"w": 2, "s": 2}},
  ...
]

"w" = window index (0 = first {window_size} seconds, 1 = next {window_size} seconds, etc.)
"s" = crowd reaction score for that window:

  0 = NO crowd reaction. Someone is TALKING and the audience is QUIET. This is the DEFAULT state.
  1 = LIGHT crowd reaction — scattered chuckles, a few people laughing
  2 = MODERATE — clear audible laughter from a decent portion of the crowd
  3 = BIG LAUGHS — strong, loud laughter filling the room, or sustained applause
  4 = ROARING — explosive laughter, entire room erupting, thunderous applause

CRITICAL RULES:
- Most windows should be 0 (someone talking, audience quiet).
- Only score > 0 when you hear DISTINCT crowd laughter, applause, cheering.
- When in doubt, score LOWER not higher.

Return exactly {num_windows} entries in order. w must go from 0 to {num_windows - 1}.
"""

    uploaded = client.files.upload(file=AUDIO_PATH)
    try:
        for _ in range(120):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt, uploaded],
            config={
                "response_mime_type": "application/json",
                "http_options": {"timeout": 120000},
            },
        )
        raw = (response.text or "").strip()
        windows = json.loads(raw)
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    # Expand to per-second
    timeline = [0] * DURATION
    for w in windows:
        idx = w.get("w", 0)
        score = w.get("s", 0)
        start = idx * window_size
        for s in range(start, min(start + window_size, DURATION)):
            timeline[s] = score

    return timeline


def run_gemini_events() -> list[int]:
    """Run Gemini Flash with event-based start/end timestamps."""
    from google import genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
Listen to this audio and identify every instance of crowd laughter, applause, cheering, or groaning.
Log the precise start and end time IN TOTAL SECONDS from the start of the audio.

Return ONLY a JSON array:
[
  {{"start_seconds": 125, "end_seconds": 130, "type": "laughter", "intensity": "big"}},
  ...
]

- Timestamps must be in TOTAL SECONDS (e.g. 5 minutes 30 seconds = 330)
- intensity: "light", "moderate", "big", "roaring"
- type: "laughter", "applause", "cheering", "groaning"
- Be exhaustive. Timestamp precision matters.
- The audio is approximately {DURATION} seconds long.
"""

    uploaded = client.files.upload(file=AUDIO_PATH)
    try:
        for _ in range(120):
            info = client.files.get(name=uploaded.name or "")
            if info.state == "ACTIVE":
                break
            time.sleep(1)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt, uploaded],
            config={
                "response_mime_type": "application/json",
                "http_options": {"timeout": 120000},
            },
        )
        raw = (response.text or "").strip()
        events = json.loads(raw)
    finally:
        try:
            client.files.delete(name=uploaded.name or "")
        except Exception:
            pass

    intensity_map = {"light": 1, "moderate": 2, "big": 3, "roaring": 4}
    timeline = [0] * DURATION
    for e in events:
        start = int(e.get("start_seconds", 0))
        end = int(e.get("end_seconds", start))
        score = intensity_map.get(e.get("intensity", "moderate"), 2)
        for s in range(max(0, start), min(DURATION, end)):
            timeline[s] = max(timeline[s], score)

    return timeline


# ─── Method: YAMNet ─────────────────────────────────────────────────────────

def run_yamnet(threshold: float = 0.15) -> list[int]:
    """Run YAMNet on the test clip. Returns per-second binary timeline."""
    import numpy as np

    # Convert to WAV first
    wav_path = Path(__file__).parent / "test_clip_16k.wav"
    if not wav_path.exists():
        subprocess.run([
            "ffmpeg", "-y", "-i", str(AUDIO_PATH),
            "-ar", "16000", "-ac", "1", str(wav_path),
        ], capture_output=True)

    import tensorflow_hub as hub
    import scipy.io.wavfile as wavmod

    model = hub.load("https://tfhub.dev/google/yamnet/1")
    sample_rate, audio_data = wavmod.read(str(wav_path))

    if audio_data.dtype == np.int16:
        audio_data = audio_data.astype(np.float32) / 32768.0

    scores, _, _ = model(audio_data)
    scores = scores.numpy()

    # YAMNet: 0.48s hop. Laughter classes: 13, 14
    frame_duration = 0.48
    timeline = [0] * DURATION
    for i, frame_scores in enumerate(scores):
        max_score = max(frame_scores[13], frame_scores[14])
        if max_score >= threshold:
            sec = int(i * frame_duration)
            if sec < DURATION:
                # Map confidence to 1-4 scale
                if max_score >= 0.6:
                    timeline[sec] = 4
                elif max_score >= 0.4:
                    timeline[sec] = 3
                elif max_score >= 0.25:
                    timeline[sec] = 2
                else:
                    timeline[sec] = max(timeline[sec], 1)

    return timeline


# ─── Method: HuggingFace laughter detection ──────────────────────────────────

def run_hf_ast() -> list[int]:
    """Run MIT Audio Spectrogram Transformer (finetuned on AudioSet).

    Has 527 classes including laughter. Transformer-based, potentially
    more accurate than YAMNet's older MobileNet architecture.

    Uses 5-second windows for CPU-feasible speed, sigmoid (multi-label),
    and aggregates all laughter-related AudioSet classes.

    Install: pip install transformers torch librosa
    """
    import torch
    import librosa
    from transformers import ASTFeatureExtractor, ASTForAudioClassification

    model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"
    extractor = ASTFeatureExtractor.from_pretrained(model_name)
    model = ASTForAudioClassification.from_pretrained(model_name)
    model.eval()

    # AudioSet laughter+applause class indices
    # 16=Laughter, 18=Giggle, 19=Snicker, 20=Belly laugh, 21=Chuckle/chortle
    laugh_indices = []
    applause_indices = []
    for idx, label in model.config.id2label.items():
        idx = int(idx)
        low = label.lower()
        if "laugh" in low or "giggle" in low or "snicker" in low or "chuckle" in low or "chortle" in low:
            laugh_indices.append(idx)
        elif "applause" in low or "cheering" in low:
            applause_indices.append(idx)

    all_reaction_indices = laugh_indices + applause_indices
    print(f"  Laughter indices: {laugh_indices} ({[model.config.id2label[i] for i in laugh_indices]})")
    print(f"  Applause indices: {applause_indices} ({[model.config.id2label[i] for i in applause_indices]})")

    if not all_reaction_indices:
        print("  WARNING: No laughter/applause labels found")
        return [0] * DURATION

    target_sr = 16000
    audio, sr = librosa.load(str(AUDIO_PATH), sr=target_sr)

    # Process in 5-second windows (much faster on CPU than 1s)
    window_sec = 5
    window_samples = target_sr * window_sec
    timeline = [0] * DURATION

    num_windows = len(audio) // window_samples
    print(f"  Processing {num_windows} windows ({window_sec}s each)...")

    for w_idx in range(num_windows):
        start_sample = w_idx * window_samples
        chunk = audio[start_sample:start_sample + window_samples]
        inputs = extractor(chunk, sampling_rate=target_sr, return_tensors="pt")

        with torch.no_grad():
            logits = model(**inputs).logits
            # AudioSet is multi-label — use sigmoid, not softmax
            probs = torch.sigmoid(logits)[0]

        max_laugh = max(probs[i].item() for i in all_reaction_indices)

        # Map to 0-4 score and fill all seconds in this window
        if max_laugh > 0.1:
            if max_laugh >= 0.5:
                score = 4
            elif max_laugh >= 0.3:
                score = 3
            elif max_laugh >= 0.2:
                score = 2
            else:
                score = 1

            start_sec = w_idx * window_sec
            for s in range(start_sec, min(start_sec + window_sec, DURATION)):
                timeline[s] = max(timeline[s], score)

        if (w_idx + 1) % 20 == 0:
            print(f"    {w_idx + 1}/{num_windows} windows done")

    return timeline


# ─── Display ─────────────────────────────────────────────────────────────────

def show_timeline(name: str, timeline: list[int], duration: int):
    chars = {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}
    print(f"\n  {name}:")
    for m in range(duration // 60 + 1):
        start = m * 60
        end = min(start + 60, duration)
        if start >= duration:
            break
        bar = "".join(chars.get(timeline[s], "?") for s in range(start, end))
        print(f"    {m:2d}:00 |{bar}|")


def show_comparison_table(results: dict, ground_truth: list[int]):
    print(f"\n{'='*80}")
    print(f"RESULTS vs GROUND TRUTH")
    print(f"{'='*80}")
    print(f"{'Method':<22} {'Prec':>6} {'Rec':>6} {'F1':>6} {'F1±1s':>6} {'F1±2s':>6} {'Active%':>8} {'Time':>7}")
    print(f"{'-'*22} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*7}")

    for name, info in sorted(results.items()):
        tl = info["timeline"]
        s0 = score_timeline(tl, ground_truth, tolerance=0)
        s1 = score_timeline(tl, ground_truth, tolerance=1)
        s2 = score_timeline(tl, ground_truth, tolerance=2)
        elapsed = info.get("elapsed", 0)
        print(f"{name:<22} {s0['precision']:>5.0%} {s0['recall']:>5.0%} {s0['f1']:>5.0%} {s1['f1']:>5.0%} {s2['f1']:>5.0%} {s0['active_pred_pct']:>7.1f}% {elapsed:>6.1f}s")

    truth_active = sum(1 for s in ground_truth if s > 0)
    print(f"\n  Ground truth: {truth_active}/{len(ground_truth)}s active ({truth_active/len(ground_truth)*100:.1f}%)")


# ─── Hybrid methods ──────────────────────────────────────────────────────────

def run_hybrid_union() -> list[int]:
    """Union of YAMNet + Gemini events. Fires if EITHER detects laughter."""
    results = json.load(open(RESULTS_PATH))
    yamnet_tl = results["yamnet"]["timeline"]
    gemini_tl = results["gemini_events"]["timeline"]
    return [max(yamnet_tl[i], gemini_tl[i]) for i in range(DURATION)]


def run_hybrid_intersect() -> list[int]:
    """Intersection: Gemini events, but boosted where YAMNet agrees."""
    results = json.load(open(RESULTS_PATH))
    yamnet_tl = results["yamnet"]["timeline"]
    gemini_tl = results["gemini_events"]["timeline"]
    timeline = [0] * DURATION
    for i in range(DURATION):
        if gemini_tl[i] > 0 and yamnet_tl[i] > 0:
            timeline[i] = max(gemini_tl[i], yamnet_tl[i])
        elif gemini_tl[i] > 0:
            timeline[i] = gemini_tl[i]
    return timeline


def run_yamnet_loose() -> list[int]:
    """YAMNet with lower threshold (0.05 instead of 0.15)."""
    return run_yamnet(threshold=0.05)


def run_hybrid_yamnet_boost() -> list[int]:
    """Gemini events as base, extend ±2s around any YAMNet hit."""
    results = json.load(open(RESULTS_PATH))
    yamnet_tl = results["yamnet"]["timeline"]
    gemini_tl = results["gemini_events"]["timeline"]
    timeline = list(gemini_tl)

    # Anywhere YAMNet fires, also activate ±2s neighbors from Gemini
    for i in range(DURATION):
        if yamnet_tl[i] > 0:
            for j in range(max(0, i - 2), min(DURATION, i + 3)):
                if timeline[j] == 0:
                    timeline[j] = 1
    return timeline


def run_consensus() -> list[int]:
    """Consensus: flag a second if >=2 of {gemini_events, yamnet, hf_ast} agree."""
    results = json.load(open(RESULTS_PATH))
    methods = ["gemini_events", "yamnet", "hf_ast"]
    timelines = [results[m]["timeline"] for m in methods]
    timeline = [0] * DURATION
    for i in range(DURATION):
        votes = sum(1 for tl in timelines if tl[i] > 0)
        if votes >= 2:
            timeline[i] = max(tl[i] for tl in timelines if tl[i] > 0)
        elif votes == 1:
            timeline[i] = 0
    return timeline


# ─── Registry ────────────────────────────────────────────────────────────────

METHODS = {
    "gemini_5s":       ("Gemini Flash 5s windows",  lambda: run_gemini_windows(5)),
    "gemini_2s":       ("Gemini Flash 2s windows",  lambda: run_gemini_windows(2)),
    "gemini_1s":       ("Gemini Flash 1s windows",  lambda: run_gemini_windows(1)),
    "gemini_events":   ("Gemini Flash events",      run_gemini_events),
    "yamnet":          ("YAMNet (TF Hub)",           run_yamnet),
    "yamnet_loose":    ("YAMNet loose (0.05)",       run_yamnet_loose),
    "hf_ast":          ("HF AST AudioSet",          run_hf_ast),
    "hybrid_union":    ("Hybrid union (evt+ym)",     run_hybrid_union),
    "hybrid_intersect":("Hybrid intersect",          run_hybrid_intersect),
    "hybrid_ym_boost": ("Hybrid YAMNet boost",       run_hybrid_yamnet_boost),
    "consensus":       ("Consensus (2/3 agree)",     run_consensus),
}


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Score laughter detection methods against ground truth")
    parser.add_argument("--methods", nargs="+", choices=list(METHODS.keys()) + ["all"],
                        default=["all"], help="Methods to run")
    parser.add_argument("--score-only", action="store_true",
                        help="Just score cached results, don't re-run methods")
    args = parser.parse_args()

    if not GROUND_TRUTH_PATH.exists():
        print(f"ERROR: No ground truth found at {GROUND_TRUTH_PATH}")
        print(f"Run label_laughter.py first to create it.")
        sys.exit(1)

    with open(GROUND_TRUTH_PATH) as f:
        gt_data = json.load(f)
    ground_truth = gt_data["timeline"]
    print(f"Ground truth loaded: {gt_data['duration']}s, {gt_data['laughter_pct']}% active")

    # Load cached results if score-only
    if args.score_only:
        if not RESULTS_PATH.exists():
            print("ERROR: No cached results. Run without --score-only first.")
            sys.exit(1)
        with open(RESULTS_PATH) as f:
            results = json.load(f)
        show_comparison_table(results, ground_truth)
        return

    methods_to_run = list(METHODS.keys()) if "all" in args.methods else args.methods

    # Load existing results to preserve previous runs
    results = {}
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            results = json.load(f)

    for method_id in methods_to_run:
        label, runner = METHODS[method_id]
        print(f"\n{'='*60}")
        print(f"Running: {label} ({method_id})")
        print(f"{'='*60}")

        try:
            t0 = time.time()
            timeline = runner()
            elapsed = time.time() - t0

            results[method_id] = {
                "label": label,
                "timeline": timeline,
                "elapsed": elapsed,
            }

            show_timeline(label, timeline, DURATION)
            s = score_timeline(timeline, ground_truth)
            print(f"\n  Precision: {s['precision']:.0%}  Recall: {s['recall']:.0%}  F1: {s['f1']:.0%}")
            print(f"  Active: {s['active_pred_pct']:.1f}% predicted vs {s['active_truth_pct']:.1f}% truth")
            print(f"  Time: {elapsed:.1f}s")

        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()

        # Rate limit pause between Gemini calls
        if method_id.startswith("gemini_") and method_id != methods_to_run[-1]:
            next_method = methods_to_run[methods_to_run.index(method_id) + 1] if methods_to_run.index(method_id) + 1 < len(methods_to_run) else ""
            if next_method.startswith("gemini_"):
                print("\n  Waiting 10s for rate limit...")
                time.sleep(10)

    # Save all results
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {RESULTS_PATH}")

    # Final comparison
    show_comparison_table(results, ground_truth)


if __name__ == "__main__":
    main()
