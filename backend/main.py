from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from database import (
    get_crowd_reaction_distribution,
    get_episode,
    get_episodes,
    get_guest_detail,
    get_guest_stats,
    get_laughter_timeline,
    get_set,
    get_sets,
    get_stats,
    get_top_comedians,
    get_topic_stats,
    get_topic_timeline,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "data" / "kill_tony.db")))

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(
    title="Kill Tony DB",
    description="API for the Kill Tony comedy database — every 1-minute set, scored and analyzed.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Stats (hero section) ──


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    return get_stats(DB_PATH)


# ── Episodes ──


@app.get("/api/episodes")
def episodes_list() -> list[dict[str, Any]]:
    return get_episodes(DB_PATH)


@app.get("/api/episodes/{episode_number}")
def episode_detail(episode_number: int) -> dict[str, Any]:
    ep = get_episode(DB_PATH, episode_number)
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    sets_data = get_sets(DB_PATH, episode_number=episode_number, sort_by="set_number", order="asc", limit=100)
    return {"episode": ep, "sets": sets_data["sets"]}


# ── Sets ──


@app.get("/api/sets")
def sets_list(
    episode: Optional[int] = Query(None, description="Filter by episode number"),
    comedian: Optional[str] = Query(None, description="Search by comedian name"),
    status: Optional[str] = Query(None, description="Filter by status: bucket_pull or regular"),
    since: Optional[str] = Query(None, description="Filter by episode date >= YYYYMMDD"),
    sort: str = Query("kill_score", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    return get_sets(
        DB_PATH,
        episode_number=episode,
        comedian_name=comedian,
        status=status,
        since=since,
        sort_by=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@app.get("/api/sets/{set_id}")
def set_detail(set_id: str) -> dict[str, Any]:
    s = get_set(DB_PATH, set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    return s


# ── Leaderboards & Aggregations ──


@app.get("/api/comedians/top")
def top_comedians(limit: int = Query(25, ge=1, le=100)) -> list[dict[str, Any]]:
    return get_top_comedians(DB_PATH, limit=limit)


@app.get("/api/topics")
def topic_stats() -> list[dict[str, Any]]:
    return get_topic_stats(DB_PATH)


@app.get("/api/topics/timeline")
def topic_timeline() -> list[dict[str, Any]]:
    return get_topic_timeline(DB_PATH)


@app.get("/api/guests")
def guest_stats() -> dict[str, Any]:
    return get_guest_stats(DB_PATH)


@app.get("/api/guests/{guest_name}")
def guest_detail(guest_name: str) -> dict[str, Any]:
    g = get_guest_detail(DB_PATH, guest_name)
    if not g:
        raise HTTPException(status_code=404, detail="Guest not found")
    return g


@app.get("/api/episodes/{episode_number}/laughter-timeline")
def laughter_timeline(episode_number: int) -> dict[str, Any]:
    data = get_laughter_timeline(DB_PATH, episode_number)
    if not data:
        raise HTTPException(status_code=404, detail="No laughter data for this episode")
    return data


@app.get("/api/crowd-reactions")
def crowd_reactions() -> list[dict[str, Any]]:
    return get_crowd_reaction_distribution(DB_PATH)


# ── Admin ──

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


@app.post("/admin/upload-db")
async def upload_db(
    file: UploadFile,
    x_admin_secret: str = Header(default=""),
) -> dict[str, str]:
    if not _ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="Admin endpoint disabled (ADMIN_SECRET not set)")
    if x_admin_secret != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    with tmp.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    tmp.replace(DB_PATH)
    return {"status": "ok", "path": str(DB_PATH)}
