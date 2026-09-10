from __future__ import annotations

import hmac
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from stat_card import get_or_render_card
from database import (
    get_crowd_reaction_distribution,
    get_episode,
    get_episodes,
    get_guest_detail,
    get_guest_stats,
    get_laughter_timeline,
    get_set,
    get_sets,
    get_sets_stats,
    get_stats,
    get_top_comedians,
    get_topic_stats,
    get_topic_timeline,
)
from votes import (
    VoteError,
    get_leaderboard,
    get_matchup,
    get_vote_stats,
    get_voter_stats,
    init_votes_db,
    record_vote,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "data" / "kill_tony.db")))
# Votes are user-generated and must survive /admin/upload-db, which replaces DB_PATH wholesale.
VOTES_DB_PATH = Path(os.environ.get("VOTES_DB_PATH", str(DB_PATH.parent / "votes.db")))
init_votes_db(VOTES_DB_PATH)

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
    allow_methods=["GET", "POST"],
    allow_headers=["x-admin-secret", "content-type"],
)

from fastapi.responses import JSONResponse  # noqa: E402
from starlette.requests import Request  # noqa: E402


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
def episodes_list(with_data: bool = Query(False, description="Only return episodes with processed sets")) -> list[dict[str, Any]]:
    return get_episodes(DB_PATH, with_data_only=with_data)


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


@app.get("/api/sets/stats")
def sets_stats(
    since: Optional[str] = Query(None, description="Filter by episode date >= YYYYMMDD"),
    episode: Optional[int] = Query(None, description="Filter by episode number"),
) -> dict[str, Any]:
    return get_sets_stats(DB_PATH, since=since, episode_number=episode)


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


@app.get("/api/guests/{guest_name}/card.png")
def guest_card(guest_name: str) -> Response:
    g = get_guest_detail(DB_PATH, guest_name)
    if not g:
        raise HTTPException(status_code=404, detail="Guest not found")
    png_bytes = get_or_render_card(g)
    return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/episodes/{episode_number}/laughter-timeline")
def laughter_timeline(episode_number: int) -> dict[str, Any]:
    data = get_laughter_timeline(DB_PATH, episode_number)
    if not data:
        raise HTTPException(status_code=404, detail="No laughter data for this episode")
    return data


@app.get("/api/crowd-reactions")
def crowd_reactions() -> list[dict[str, Any]]:
    return get_crowd_reaction_distribution(DB_PATH)


# ── Head-to-head voting ──


class VoteIn(BaseModel):
    set_a: str = Field(min_length=1, max_length=32)
    set_b: str = Field(min_length=1, max_length=32)
    winner: str = Field(min_length=1, max_length=32)
    voter_id: str = Field(min_length=8, max_length=64)


@app.exception_handler(VoteError)
async def vote_error(request: Request, exc: VoteError) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(status_code=exc.status, content={"detail": exc.detail})


@app.get("/api/vote/matchup")
def vote_matchup(voter_id: str = Query(min_length=8, max_length=64)) -> dict[str, Any]:
    return {**get_matchup(DB_PATH, VOTES_DB_PATH, voter_id), "voter": get_voter_stats(VOTES_DB_PATH, voter_id)}


@app.post("/api/vote")
def vote_submit(body: VoteIn) -> dict[str, Any]:
    return record_vote(
        DB_PATH, VOTES_DB_PATH, set_a=body.set_a, set_b=body.set_b, winner=body.winner, voter_id=body.voter_id
    )


@app.get("/api/vote/leaderboard")
def vote_leaderboard(
    min_matchups: int = Query(20, ge=1, le=1000),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return get_leaderboard(DB_PATH, VOTES_DB_PATH, min_matchups=min_matchups, limit=limit)


@app.get("/api/vote/stats")
def vote_stats() -> dict[str, Any]:
    return get_vote_stats(VOTES_DB_PATH)


# ── Admin ──

_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")


@app.post("/admin/upload-db")
async def upload_db(
    file: UploadFile,
    x_admin_secret: str = Header(default=""),
) -> dict[str, str]:
    if not _ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="Admin endpoint disabled (ADMIN_SECRET not set)")
    if not hmac.compare_digest(x_admin_secret, _ADMIN_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    MAX_DB_SIZE = 500 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_DB_SIZE:
        raise HTTPException(status_code=413, detail="File too large (500MB limit)")
    if content[:16] != b"SQLite format 3\x00":
        raise HTTPException(status_code=400, detail="Not a valid SQLite database")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    tmp.write_bytes(content)
    try:
        conn = sqlite3.connect(str(tmp))
        conn.execute("SELECT count(*) FROM sqlite_master")
        conn.close()
    except sqlite3.DatabaseError:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Corrupt SQLite database")
    tmp.replace(DB_PATH)
    return {"status": "ok"}
