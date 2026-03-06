from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import requests

from audio_transcriber import AudioTranscriptionError, transcribe_youtube_audio_with_gemini

class TranscriptError(RuntimeError):
    pass


@dataclass
class TranscriptResult:
    video_id: str
    entries: list[dict[str, Any]]
    source: str


def extract_video_id(youtube_url: str) -> str:
    parsed = urlparse(youtube_url)
    if parsed.hostname in {"youtu.be"}:
        video_id = parsed.path.lstrip("/")
        if video_id:
            return video_id

    if parsed.hostname and "youtube.com" in parsed.hostname:
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            video_id = query.get("v", [""])[0]
            if video_id:
                return video_id
        match = re.match(r"/embed/([^/?]+)", parsed.path)
        if match:
            return match.group(1)
        match = re.match(r"/shorts/([^/?]+)", parsed.path)
        if match:
            return match.group(1)

    raise TranscriptError("Unable to parse YouTube video ID")


def fetch_transcript(youtube_url: str, transcription_model: str | None = None) -> TranscriptResult:
    video_id = extract_video_id(youtube_url)
    errors: list[str] = []

    try:
        entries = _fetch_with_youtube_transcript_api(video_id)
        return TranscriptResult(video_id=video_id, entries=entries, source="youtube_transcript_api")
    except Exception as exc:
        errors.append(f"youtube_transcript_api: {exc}")

    try:
        entries = _fetch_with_yt_dlp(youtube_url)
        return TranscriptResult(video_id=video_id, entries=entries, source="yt_dlp")
    except Exception as exc:
        errors.append(f"yt_dlp: {exc}")

    try:
        entries = transcribe_youtube_audio_with_gemini(
            youtube_url,
            model=transcription_model or "gemini-3-flash-preview",
        )
        return TranscriptResult(video_id=video_id, entries=entries, source="gemini_audio_fallback")
    except AudioTranscriptionError as exc:
        errors.append(f"gemini_audio_fallback: {exc}")
        raise TranscriptError(f"Failed to fetch transcript. Attempts: {'; '.join(errors)}") from exc


def _fetch_with_youtube_transcript_api(video_id: str) -> list[dict[str, Any]]:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

    try:
        return YouTubeTranscriptApi.get_transcript(video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        for candidate in transcript_list:
            if candidate.language_code.startswith("en"):
                transcript = candidate
                break
        if transcript is None:
            transcript = transcript_list.find_transcript(["en"])
        return transcript.fetch()


def _fetch_with_yt_dlp(youtube_url: str) -> list[dict[str, Any]]:
    from yt_dlp import YoutubeDL

    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "nocheckcertificate": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)

    subtitles = _filter_non_transcript_languages(info.get("subtitles") or {})
    automatic_captions = _filter_non_transcript_languages(info.get("automatic_captions") or {})

    caption_sets: list[tuple[str, dict[str, Any]]] = []
    if subtitles:
        caption_sets.append(("subtitles", subtitles))
    if automatic_captions:
        caption_sets.append(("automatic_captions", automatic_captions))

    if not caption_sets:
        raise TranscriptError("No subtitles or automatic captions found")

    errors: list[str] = []
    for source, captions in caption_sets:
        lang_key = _pick_caption_language(captions)
        tracks = _ordered_caption_tracks(captions[lang_key])

        for track in tracks:
            try:
                response = requests.get(track["url"], timeout=30)
                response.raise_for_status()
                return _parse_caption_payload(response.text, track.get("ext"))
            except Exception as exc:
                errors.append(f"{source}/{lang_key}/{track.get('ext')}: {exc}")

    raise TranscriptError(f"Could not parse captions. Tried: {'; '.join(errors[:5])}")


def _filter_non_transcript_languages(captions: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for language, tracks in captions.items():
        key = language.lower()
        if "live_chat" in key:
            continue
        filtered[language] = tracks
    return filtered


def _pick_caption_language(captions: dict[str, Any]) -> str:
    preferred = ["en", "en-US", "en-GB", "en-CA", "en-AU"]
    for key in preferred:
        if key in captions:
            return key
    return sorted(captions.keys())[0]


def _pick_caption_track(tracks: Iterable[dict[str, Any]]) -> dict[str, Any]:
    tracks = list(tracks)
    for ext in ("vtt", "json3", "srv3", "ttml"):
        for track in tracks:
            if track.get("ext") == ext:
                return track
    return tracks[0]


def _ordered_caption_tracks(tracks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer JSON3 first: it includes timing + cleaner segmented text.
    preferred_exts = ("json3", "vtt", "ttml", "srv3", "srv2", "srv1", "json")
    remaining = list(tracks)
    ordered: list[dict[str, Any]] = []
    for ext in preferred_exts:
        matching = [t for t in remaining if t.get("ext") == ext]
        ordered.extend(matching)
        remaining = [t for t in remaining if t.get("ext") != ext]
    ordered.extend(remaining)
    return ordered


def _parse_caption_payload(raw: str, ext: str | None) -> list[dict[str, Any]]:
    ext = (ext or "").lower()
    if ext == "json3":
        return _parse_json3(raw)
    if ext in {"srv3", "srv2", "srv1", "ttml"}:
        return _parse_xml_timedtext(raw)
    if ext == "vtt":
        return _parse_vtt(raw)

    trimmed = raw.lstrip()
    if trimmed.startswith("{"):
        return _parse_json3(raw)
    if "-->" in raw:
        return _parse_vtt(raw)
    if "<transcript" in raw or "<timedtext" in raw:
        return _parse_xml_timedtext(raw)
    raise TranscriptError(f"Unsupported caption format: {ext or 'unknown'}")


def _parse_vtt(vtt_text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lines = vtt_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_raw, end_raw = line.split("-->")[:2]
            start = _parse_timestamp(start_raw.strip())
            end = _parse_timestamp(end_raw.strip().split(" ")[0])
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            text = " ".join(text_lines).strip()
            if text:
                text = _clean_caption_text(text)
                if text:
                    entries.append({"start": start, "duration": max(0.0, end - start), "text": text})
        i += 1

    if not entries:
        raise TranscriptError("No cues parsed from VTT")
    return entries


def _parse_json3(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    entries: list[dict[str, Any]] = []

    for event in data.get("events", []):
        if "segs" not in event:
            continue
        start_ms = event.get("tStartMs")
        dur_ms = event.get("dDurationMs")
        if start_ms is None or dur_ms is None:
            continue
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", []))
        text = _clean_caption_text(text.replace("\n", " ").strip())
        if not text:
            continue
        entries.append(
            {
                "start": start_ms / 1000.0,
                "duration": dur_ms / 1000.0,
                "text": text,
            }
        )

    if not entries:
        raise TranscriptError("No cues parsed from JSON3")
    return entries


def _parse_xml_timedtext(raw: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise TranscriptError(f"Invalid XML captions: {exc}") from exc

    for node in root.iter("p"):
        start_raw = node.attrib.get("t")
        duration_raw = node.attrib.get("d")
        if start_raw is None or duration_raw is None:
            continue

        text = "".join(node.itertext())
        text = _clean_caption_text(text)
        if not text:
            continue

        entries.append(
            {
                "start": int(start_raw) / 1000.0,
                "duration": int(duration_raw) / 1000.0,
                "text": text,
            }
        )

    if not entries:
        raise TranscriptError("No cues parsed from XML captions")
    return entries


def _parse_timestamp(value: str) -> float:
    value = value.strip().replace(",", ".")
    if not value:
        return 0.0

    if ":" not in value:
        return float(value)

    parts = value.split(":")
    parts = [p.strip() for p in parts]
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    else:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    return hours * 3600 + minutes * 60 + seconds


def _clean_caption_text(value: str) -> str:
    # Remove inline styling tags from timed captions and normalize whitespace.
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value
