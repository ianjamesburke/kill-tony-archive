"""Head-to-head set voting with Elo ratings.

Votes live in their own SQLite file (VOTES_DB_PATH), never in kill_tony.db.
The main DB is replaced wholesale by /admin/upload-db on every pipeline sync,
so anything user-generated must be stored beside it, not inside it.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ELO_START = 1500.0
ELO_K = 32.0
ELO_WINDOW = 200.0          # opponent must be within this many points when possible
UNDERVOTED_POOL = 0.1       # set A is drawn from the least-voted 10% of eligible sets
MAX_VOTES_PER_DAY = 300
LEADERBOARD_MIN_MATCHUPS = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS votes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_key   TEXT NOT NULL,           -- "{low_set_id}|{high_set_id}", order-independent
    set_a      TEXT NOT NULL,
    set_b      TEXT NOT NULL,
    winner     TEXT NOT NULL,
    voter_id   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (voter_id, pair_key)
);
CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_id, created_at);

CREATE TABLE IF NOT EXISTS ratings (
    set_id   TEXT PRIMARY KEY,
    elo      REAL NOT NULL,
    wins     INTEGER NOT NULL DEFAULT 0,
    losses   INTEGER NOT NULL DEFAULT 0
);
"""


class VoteError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_votes_db(votes_path: Path) -> None:
    votes_path.parent.mkdir(parents=True, exist_ok=True)
    with _conn(votes_path) as conn:
        conn.executescript(_SCHEMA)


def _pair_key(a: str, b: str) -> str:
    lo, hi = sorted((a, b))
    return f"{lo}|{hi}"


# ── Eligible sets (read from the main DB) ──


_SET_COLS = """
    s.set_id, s.comedian_name, s.episode_number, s.set_number,
    s.set_start_seconds, s.set_end_seconds, s.set_transcript,
    s.kill_score, s.golden_ticket, e.video_id
"""


def _eligible_sets(main_path: Path) -> list[dict[str, Any]]:
    with _conn(main_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {_SET_COLS},
                   RANK() OVER (ORDER BY s.kill_score DESC) AS kill_score_rank
            FROM sets s
            JOIN episodes e ON e.episode_number = s.episode_number
            WHERE s.kill_score IS NOT NULL
              AND s.set_start_seconds IS NOT NULL
              AND s.set_end_seconds IS NOT NULL
              AND e.video_id IS NOT NULL
            """
        ).fetchall()
    return [_set_row(r) for r in rows]


def _set_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["golden_ticket"] = bool(d.get("golden_ticket"))
    transcript = d.pop("set_transcript") or ""
    d["excerpt"] = transcript[:220].strip()
    d["set_start_seconds"] = int(d["set_start_seconds"])
    d["set_end_seconds"] = int(d["set_end_seconds"])
    return d


def _ratings(votes_path: Path) -> dict[str, dict[str, Any]]:
    with _conn(votes_path) as conn:
        rows = conn.execute("SELECT set_id, elo, wins, losses FROM ratings").fetchall()
    return {r["set_id"]: dict(r) for r in rows}


def _with_rating(s: dict[str, Any], ratings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    r = ratings.get(s["set_id"], {"elo": ELO_START, "wins": 0, "losses": 0})
    return {**s, "elo": round(r["elo"]), "wins": r["wins"], "losses": r["losses"], "matchups": r["wins"] + r["losses"]}


# ── Matchup selection ──


def get_matchup(main_path: Path, votes_path: Path, voter_id: str) -> dict[str, Any]:
    sets = _eligible_sets(main_path)
    if len(sets) < 2:
        raise VoteError(503, "Not enough eligible sets to build a matchup")
    ratings = _ratings(votes_path)
    sets = [_with_rating(s, ratings) for s in sets]

    with _conn(votes_path) as conn:
        seen = {r["pair_key"] for r in conn.execute("SELECT pair_key FROM votes WHERE voter_id = ?", (voter_id,))}

    sets.sort(key=lambda s: s["matchups"])
    pool = sets[: max(20, int(len(sets) * UNDERVOTED_POOL))]
    random.shuffle(pool)

    for a in pool:
        unseen = [b for b in sets if b["set_id"] != a["set_id"] and _pair_key(a["set_id"], b["set_id"]) not in seen]
        if not unseen:
            continue
        near = [b for b in unseen if abs(b["elo"] - a["elo"]) <= ELO_WINDOW]
        b = random.choice(near or unseen)
        if random.random() < 0.5:
            a, b = b, a
        return {"a": a, "b": b}

    raise VoteError(409, "You have voted on every matchup available to you")


# ── Voting ──


def _expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def record_vote(main_path: Path, votes_path: Path, *, set_a: str, set_b: str, winner: str, voter_id: str) -> dict[str, Any]:
    if set_a == set_b:
        raise VoteError(400, "set_a and set_b must differ")
    if winner not in (set_a, set_b):
        raise VoteError(400, "winner must be set_a or set_b")

    with _conn(main_path) as conn:
        known = {r["set_id"] for r in conn.execute("SELECT set_id FROM sets WHERE set_id IN (?, ?)", (set_a, set_b))}
    if known != {set_a, set_b}:
        raise VoteError(404, "Unknown set id")

    loser = set_b if winner == set_a else set_a
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()

    with _conn(votes_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        recent = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE voter_id = ? AND created_at >= ?", (voter_id, day_ago)
        ).fetchone()[0]
        if recent >= MAX_VOTES_PER_DAY:
            raise VoteError(429, f"Daily vote limit reached ({MAX_VOTES_PER_DAY}). Come back tomorrow.")

        try:
            conn.execute(
                "INSERT INTO votes (pair_key, set_a, set_b, winner, voter_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (_pair_key(set_a, set_b), set_a, set_b, winner, voter_id, now.isoformat()),
            )
        except sqlite3.IntegrityError:
            raise VoteError(409, "You already voted on this matchup") from None

        for sid in (winner, loser):
            conn.execute("INSERT OR IGNORE INTO ratings (set_id, elo) VALUES (?, ?)", (sid, ELO_START))
        rows = {r["set_id"]: dict(r) for r in conn.execute("SELECT * FROM ratings WHERE set_id IN (?, ?)", (winner, loser))}
        w, l = rows[winner], rows[loser]
        delta = ELO_K * (1.0 - _expected(w["elo"], l["elo"]))
        conn.execute("UPDATE ratings SET elo = elo + ?, wins = wins + 1 WHERE set_id = ?", (delta, winner))
        conn.execute("UPDATE ratings SET elo = elo - ?, losses = losses + 1 WHERE set_id = ?", (delta, loser))
        conn.commit()

    def summary(before: dict[str, Any], won: bool) -> dict[str, Any]:
        wins = before["wins"] + (1 if won else 0)
        losses = before["losses"] + (0 if won else 1)
        after = before["elo"] + (delta if won else -delta)
        return {
            "set_id": before["set_id"],
            "elo_before": round(before["elo"]),
            "elo_after": round(after),
            "wins": wins,
            "losses": losses,
            "matchups": wins + losses,
            "win_rate": round(wins / (wins + losses), 3),
        }

    return {"winner": summary(w, True), "loser": summary(l, False)}


# ── Leaderboard ──


def get_leaderboard(
    main_path: Path,
    votes_path: Path,
    *,
    min_matchups: int = LEADERBOARD_MIN_MATCHUPS,
    limit: int = 50,
) -> dict[str, Any]:
    ratings = _ratings(votes_path)
    sets = [_with_rating(s, ratings) for s in _eligible_sets(main_path)]
    ranked = [s for s in sets if s["matchups"] >= min_matchups]
    ranked.sort(key=lambda s: -s["elo"])

    with _conn(votes_path) as conn:
        total_votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]

    out = []
    for i, s in enumerate(ranked[:limit], start=1):
        out.append({**s, "rank": i, "win_rate": round(s["wins"] / s["matchups"], 3)})
    return {
        "sets": out,
        "total_votes": total_votes,
        "ranked_count": len(ranked),
        "min_matchups": min_matchups,
    }


def get_vote_stats(votes_path: Path) -> dict[str, Any]:
    with _conn(votes_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        voters = conn.execute("SELECT COUNT(DISTINCT voter_id) FROM votes").fetchone()[0]
    return {"total_votes": total, "voters": voters}


def get_voter_stats(votes_path: Path, voter_id: str) -> dict[str, Any]:
    day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with _conn(votes_path) as conn:
        today = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE voter_id = ? AND created_at >= ?", (voter_id, day_ago)
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM votes WHERE voter_id = ?", (voter_id,)).fetchone()[0]
    return {"votes_today": today, "votes_total": total, "daily_limit": MAX_VOTES_PER_DAY}

