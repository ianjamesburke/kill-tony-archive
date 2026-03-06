from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from google import genai


class GeminiError(RuntimeError):
    pass


DEFAULT_MODEL = "gemini-3-flash-preview"

DEFAULT_PROMPT = """
You are an elite Kill Tony data extraction engine. Parse this transcript into a deep structured dataset for comedy performance research.

Return JSON only. No markdown. Strictly match this schema:
{
  "episode": {
    "episode_number": string | null,
    "episode_title": string | null,
    "date": string | null,
    "location": string | null,
    "youtube_url": string,
    "runtime_seconds": number | null,
    "guest_judges": string[],
    "band_members": string[],
    "regulars_or_special_sets": string[],
    "total_sets_detected": number,
    "total_bucket_pulls": number,
    "total_golden_ticket_winners": number,
    "total_secret_show_invites": number,
    "joke_book_tally": {
      "big_book": number,
      "small_book": number,
      "no_book": number,
      "unknown": number
    },
    "global_topic_clusters": string[],
    "overall_notes": string
  },
  "sets": [
    {
      "set_index": number,
      "comedian_name": string,
      "participant_type": "Bucket Pull" | "Golden Ticket Winner" | "Regular" | "Special Guest" | "Unknown",
      "set_start_time": "HH:MM:SS",
      "set_end_time": "HH:MM:SS",
      "interview_start_time": "HH:MM:SS" | null,
      "interview_end_time": "HH:MM:SS" | null,
      "set_transcript": string,
      "interview_transcript": string,
      "set_length_seconds": number,
      "interview_length_seconds": number,
      "set_word_count": number,
      "interview_word_count": number,
      "total_word_count": number,
      "punchline_count_estimated": number,
      "punchlines_per_minute": number,
      "joke_topics": string[],
      "topic_density_score": number,
      "archetype_tags": string[],
      "crowd_reaction": {
        "laugh_breaks_estimated": number,
        "applause_breaks_estimated": number,
        "crowd_pop_moments_estimated": number,
        "energy_score_0_to_10": number
      },
      "outcome": "Big Book" | "Small Book" | "No Book" | "Unknown",
      "joke_book_size": "Big Book" | "Small Book" | "No Book" | "Unknown",
      "secret_show_invite": boolean,
      "golden_ticket_awarded": boolean,
      "tonys_mood": "Engaged" | "Dismissive" | "Annoyed" | "Laughing" | "Unknown",
      "notable_tony_quotes": string[],
      "notable_comedian_quotes": string[],
      "bomb_index": number,
      "scorecard": {
        "total_points": number,
        "point_breakdown": {
          "book": number,
          "secret_show": number,
          "golden_ticket": number,
          "long_interview": number,
          "tony_praise": number,
          "audience_pop": number,
          "originality": number,
          "callbacks": number
        },
        "notes": string
      },
      "confidence": number
    }
  ],
  "leaderboards": {
    "highest_score_comedians": string[],
    "best_punchline_rate_comedians": string[],
    "longest_interviews": string[],
    "top_topics": string[]
  },
  "quality_notes": {
    "missing_sections": string[],
    "assumptions": string[],
    "low_confidence_fields": string[]
  }
}

Rules:
- Use transcript timestamps to segment set vs interview sections per comedian.
- Estimate punchline counts and crowd reaction signals from language cues.
- For participant_type: a comedian who pulls from the bucket and is awarded a golden ticket in THIS episode is still "Bucket Pull" (with golden_ticket_awarded=true). A comedian who is RETURNING to the show because they previously won a golden ticket should be "Regular" — Tony will typically introduce them with past-tense phrasing like "won a golden ticket" or "is back after winning". Do not label returning golden ticket winners as "Bucket Pull".
- Compute bomb_index = interview_length_seconds / max(set_length_seconds, 1).
- Archetype tags must be from [Shock Humor, Self-Deprecation, Storytelling, Observational, Chaos, Crowd Work].
- Use null/Unknown when uncertain and document assumptions.
- Include as much specific detail as possible without inventing facts.

TRANSCRIPT:
"""


@dataclass
class GeminiResult:
    model: str
    prompt: str
    data: dict[str, Any]
    raw_text: str


def analyze_transcript(
    transcript_entries: list[dict[str, Any]],
    youtube_url: str,
    prompt_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> GeminiResult:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable")

    prompt = (prompt_override or DEFAULT_PROMPT).strip()
    model = model_override or DEFAULT_MODEL

    transcript_text = _format_transcript(transcript_entries)
    full_prompt = f"{prompt}\n{transcript_text}\n"

    client = genai.Client(api_key=api_key)

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
                config={"response_mime_type": "application/json"},
            )
            raw_text = response.text or ""
            data = _safe_json_loads(raw_text)
            return GeminiResult(model=model, prompt=prompt, data=data, raw_text=raw_text)
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (2**attempt))

    raise GeminiError(f"Gemini request failed: {last_error}")


def _format_transcript(transcript_entries: list[dict[str, Any]]) -> str:
    lines = []
    for entry in transcript_entries:
        start = entry.get("start", 0.0)
        text = entry.get("text", "")
        if not text:
            continue
        timestamp = _format_timestamp(start)
        lines.append(f"[{timestamp}] {text}")
    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _safe_json_loads(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise GeminiError("Gemini returned empty response")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise GeminiError("Gemini response did not contain JSON")
        return json.loads(match.group(0))
