from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── Episodes ──


def get_episodes(db_path: Path) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *,
                   RANK() OVER (ORDER BY episode_kill_score DESC) AS episode_rank,
                   (SELECT COUNT(*) FROM episodes) AS total_episodes
            FROM (
                SELECT e.*,
                       COUNT(s.set_id) AS set_count,
                       ROUND(AVG(s.kill_score), 1) AS avg_kill_score,
                       ROUND(
                           (COALESCE(AVG(s.kill_score), 0) / 29.0) * 70
                           + (COALESCE(e.laughter_pct, 0) / 100.0) * 30,
                       1) AS episode_kill_score
                FROM episodes e
                LEFT JOIN sets s ON s.episode_number = e.episode_number
                GROUP BY e.episode_number
            )
            ORDER BY episode_number DESC
            """
        ).fetchall()
    return [_episode_row(r) for r in rows]


def get_episode(db_path: Path, episode_number: int) -> Optional[dict[str, Any]]:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM (
                SELECT e2.*,
                       COUNT(s2.set_id) AS set_count,
                       ROUND(AVG(s2.kill_score), 1) AS avg_kill_score,
                       ROUND(
                           (COALESCE(AVG(s2.kill_score), 0) / 29.0) * 70
                           + (COALESCE(e2.laughter_pct, 0) / 100.0) * 30,
                       1) AS episode_kill_score
                FROM episodes e2
                LEFT JOIN sets s2 ON s2.episode_number = e2.episode_number
                GROUP BY e2.episode_number
            ) ranked
            WHERE episode_number = ?
            """,
            (episode_number,),
        ).fetchone()
    if not row:
        return None
    d = _episode_row(row)
    # Compute rank separately (need all episodes for ranking)
    with _conn(db_path) as conn:
        rank_row = conn.execute(
            """
            SELECT COUNT(*) + 1 AS episode_rank,
                   (SELECT COUNT(*) FROM episodes) AS total_episodes
            FROM (
                SELECT e2.episode_number,
                       ROUND(
                           (COALESCE(AVG(s2.kill_score), 0) / 29.0) * 70
                           + (COALESCE(e2.laughter_pct, 0) / 100.0) * 30,
                       1) AS episode_kill_score
                FROM episodes e2
                LEFT JOIN sets s2 ON s2.episode_number = e2.episode_number
                GROUP BY e2.episode_number
            ) all_eps
            WHERE all_eps.episode_kill_score > ?
            """,
            (d["episode_kill_score"],),
        ).fetchone()
    d["episode_rank"] = rank_row["episode_rank"]
    d["total_episodes"] = rank_row["total_episodes"]
    return d


def _episode_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["guests"] = json.loads(d["guests"]) if d.get("guests") else []
    return d


# ── Sets ──


def get_sets(
    db_path: Path,
    *,
    episode_number: Optional[int] = None,
    comedian_name: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    sort_by: str = "kill_score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    where_clauses: list[str] = []
    params: list[Any] = []

    if episode_number is not None:
        where_clauses.append("s.episode_number = ?")
        params.append(episode_number)
    if comedian_name is not None:
        where_clauses.append("LOWER(s.comedian_name) LIKE ?")
        params.append(f"%{comedian_name.lower()}%")
    if status is not None:
        where_clauses.append("s.status = ?")
        params.append(status)
    if since is not None:
        where_clauses.append("e.date >= ?")
        params.append(since)

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    allowed_sorts = {
        "kill_score", "episode_number", "comedian_name",
        "crowd_reaction", "tony_praise_level", "joke_density",
        "set_number",
    }
    if sort_by not in allowed_sorts:
        sort_by = "kill_score"
    direction = "DESC" if order.lower() == "desc" else "ASC"

    with _conn(db_path) as conn:
        count_row = conn.execute(
            f"SELECT COUNT(*) AS total FROM sets s JOIN episodes e ON e.episode_number = s.episode_number {where}", params
        ).fetchone()
        total = count_row["total"]

        rows = conn.execute(
            f"""
            SELECT s.*, e.guests, e.venue, e.date,
                   (SELECT COUNT(*) + 1 FROM sets s2
                    WHERE s2.kill_score > s.kill_score
                       OR (s2.kill_score = s.kill_score AND (
                           CASE s2.crowd_reaction
                               WHEN 'roaring' THEN 4 WHEN 'big_laughs' THEN 3
                               WHEN 'moderate' THEN 2 WHEN 'light' THEN 1 ELSE 0 END
                           > CASE s.crowd_reaction
                               WHEN 'roaring' THEN 4 WHEN 'big_laughs' THEN 3
                               WHEN 'moderate' THEN 2 WHEN 'light' THEN 1 ELSE 0 END
                       ))
                       OR (s2.kill_score = s.kill_score AND (
                           CASE s2.crowd_reaction
                               WHEN 'roaring' THEN 4 WHEN 'big_laughs' THEN 3
                               WHEN 'moderate' THEN 2 WHEN 'light' THEN 1 ELSE 0 END
                           = CASE s.crowd_reaction
                               WHEN 'roaring' THEN 4 WHEN 'big_laughs' THEN 3
                               WHEN 'moderate' THEN 2 WHEN 'light' THEN 1 ELSE 0 END
                       ) AND COALESCE(s2.joke_density, 0) > COALESCE(s.joke_density, 0))
                   ) AS set_rank,
                   (SELECT COUNT(*) FROM sets) AS total_sets
            FROM sets s
            JOIN episodes e ON e.episode_number = s.episode_number
            {where}
            ORDER BY s.{sort_by} {direction} NULLS LAST, s.episode_number DESC, s.set_number ASC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    return {
        "sets": [_set_row(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_set(db_path: Path, set_id: str) -> Optional[dict[str, Any]]:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT s.*, e.guests, e.venue, e.date
            FROM sets s
            JOIN episodes e ON e.episode_number = s.episode_number
            WHERE s.set_id = ?
            """,
            (set_id,),
        ).fetchone()
    if not row:
        return None
    return _set_row(row)


def _set_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["topic_tags"] = json.loads(d["topic_tags"]) if d.get("topic_tags") else []
    d["guests"] = json.loads(d["guests"]) if d.get("guests") else []
    d["golden_ticket"] = bool(d.get("golden_ticket"))
    d["sign_up_again"] = bool(d.get("sign_up_again"))
    d["promoted_to_regular"] = bool(d.get("promoted_to_regular"))
    d["invited_secret_show"] = bool(d.get("invited_secret_show"))
    return d


# ── Aggregations ──


def get_stats(db_path: Path) -> dict[str, Any]:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM episodes) AS episode_count,
                (SELECT COUNT(*) FROM sets) AS set_count,
                (SELECT COUNT(DISTINCT comedian_name) FROM sets) AS comedian_count,
                (SELECT ROUND(AVG(kill_score), 1) FROM sets) AS avg_kill_score,
                (SELECT COUNT(*) FROM sets WHERE golden_ticket = 1) AS golden_tickets,
                (SELECT MAX(episode_number) FROM episodes) AS latest_episode
            """
        ).fetchone()
    return dict(row)


def get_top_comedians(db_path: Path, limit: int = 25) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                comedian_name,
                COUNT(*) AS appearances,
                ROUND(AVG(kill_score), 1) AS avg_kill_score,
                ROUND(MAX(kill_score), 1) AS best_kill_score,
                SUM(golden_ticket) AS golden_tickets,
                status
            FROM sets
            GROUP BY comedian_name
            ORDER BY avg_kill_score DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_topic_stats(db_path: Path) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT topic_tags FROM sets WHERE topic_tags IS NOT NULL"
        ).fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        tags = json.loads(row["topic_tags"]) if row["topic_tags"] else []
        for tag in tags:
            key = tag.strip().lower()
            if key:
                counts[key] = counts.get(key, 0) + 1

    return sorted(
        [{"topic": k, "count": v} for k, v in counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )


def get_guest_stats(db_path: Path) -> dict[str, Any]:
    with _conn(db_path) as conn:
        # Get overall bucket-pull average for comparison baseline
        baseline_row = conn.execute(
            "SELECT ROUND(AVG(kill_score), 1) AS avg FROM sets WHERE status = 'bucket_pull'"
        ).fetchone()
        baseline_bucket_avg = baseline_row["avg"] if baseline_row else 0

        episodes = conn.execute(
            """
            SELECT e.episode_number, e.guests, e.laugh_count,
                   ROUND(AVG(s.kill_score), 1) AS avg_kill_score,
                   ROUND(AVG(CASE WHEN s.status = 'bucket_pull' THEN s.kill_score END), 1)
                       AS avg_bucket_score,
                   COUNT(s.set_id) AS set_count
            FROM episodes e
            LEFT JOIN sets s ON s.episode_number = e.episode_number
            GROUP BY e.episode_number
            """
        ).fetchall()

    guest_data: dict[str, dict[str, Any]] = {}
    for ep in episodes:
        guests = json.loads(ep["guests"]) if ep["guests"] else []
        for guest in guests:
            name = guest.strip()
            if not name:
                continue
            if name not in guest_data:
                guest_data[name] = {
                    "guest_name": name,
                    "episodes": [],
                    "total_laugh_count": 0,
                    "scores": [],
                    "bucket_scores": [],
                }
            guest_data[name]["episodes"].append(ep["episode_number"])
            guest_data[name]["total_laugh_count"] += ep["laugh_count"] or 0
            if ep["avg_kill_score"] is not None:
                guest_data[name]["scores"].append(ep["avg_kill_score"])
            if ep["avg_bucket_score"] is not None:
                guest_data[name]["bucket_scores"].append(ep["avg_bucket_score"])

    result = []
    for g in guest_data.values():
        scores = g.pop("scores")
        bucket_scores = g.pop("bucket_scores")
        g["episode_count"] = len(g["episodes"])
        g["avg_kill_score"] = round(sum(scores) / len(scores), 1) if scores else None
        g["avg_bucket_score"] = (
            round(sum(bucket_scores) / len(bucket_scores), 1) if bucket_scores else None
        )
        g["bucket_lift"] = (
            round(g["avg_bucket_score"] - baseline_bucket_avg, 1)
            if g["avg_bucket_score"] is not None and baseline_bucket_avg
            else None
        )
        result.append(g)

    return {
        "guests": sorted(result, key=lambda x: x.get("avg_kill_score") or 0, reverse=True),
        "baseline_bucket_avg": baseline_bucket_avg,
    }


def get_guest_detail(db_path: Path, guest_name: str) -> Optional[dict[str, Any]]:
    with _conn(db_path) as conn:
        episodes = conn.execute(
            """
            SELECT e.episode_number, e.guests, e.laugh_count, e.date, e.venue,
                   ROUND(AVG(s.kill_score), 1) AS avg_kill_score,
                   ROUND(AVG(CASE WHEN s.status = 'bucket_pull' THEN s.kill_score END), 1)
                       AS avg_bucket_score,
                   COUNT(s.set_id) AS set_count,
                   SUM(CASE WHEN s.crowd_reaction IN ('big_laughs', 'roaring') THEN 1 ELSE 0 END)
                       AS hot_sets
            FROM episodes e
            LEFT JOIN sets s ON s.episode_number = e.episode_number
            GROUP BY e.episode_number
            """
        ).fetchall()

        baseline_row = conn.execute(
            "SELECT ROUND(AVG(kill_score), 1) AS avg FROM sets WHERE status = 'bucket_pull'"
        ).fetchone()
        baseline = baseline_row["avg"] if baseline_row else 0

    guest_episodes = []
    for ep in episodes:
        guests = json.loads(ep["guests"]) if ep["guests"] else []
        if guest_name in [g.strip() for g in guests]:
            guest_episodes.append({
                "episode_number": ep["episode_number"],
                "date": ep["date"],
                "venue": ep["venue"],
                "guests": [g.strip() for g in guests],
                "laugh_count": ep["laugh_count"],
                "avg_kill_score": ep["avg_kill_score"],
                "avg_bucket_score": ep["avg_bucket_score"],
                "set_count": ep["set_count"],
                "hot_sets": ep["hot_sets"],
            })

    if not guest_episodes:
        return None

    scores = [e["avg_kill_score"] for e in guest_episodes if e["avg_kill_score"] is not None]
    bucket_scores = [e["avg_bucket_score"] for e in guest_episodes if e["avg_bucket_score"] is not None]
    laughs = [e["laugh_count"] for e in guest_episodes if e["laugh_count"] is not None]

    return {
        "guest_name": guest_name,
        "episodes": guest_episodes,
        "episode_count": len(guest_episodes),
        "avg_kill_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_bucket_score": round(sum(bucket_scores) / len(bucket_scores), 1) if bucket_scores else None,
        "avg_laugh_count": round(sum(laughs) / len(laughs), 1) if laughs else None,
        "total_laugh_count": sum(laughs),
        "baseline_bucket_avg": baseline,
    }


def get_laughter_timeline(db_path: Path, episode_number: int, bucket_seconds: int = 5) -> Optional[dict[str, Any]]:
    """Return bucketed laughter intensity + set boundaries for timeline visualization."""
    with _conn(db_path) as conn:
        frames = conn.execute(
            "SELECT time_seconds, score FROM laughter_frames WHERE episode_number = ? ORDER BY time_seconds",
            (episode_number,),
        ).fetchall()

        if not frames:
            return None

        sets = conn.execute(
            "SELECT set_id, set_number, comedian_name, set_start_seconds, set_end_seconds, status "
            "FROM sets WHERE episode_number = ? ORDER BY set_start_seconds",
            (episode_number,),
        ).fetchall()

        ep = conn.execute(
            "SELECT total_laughter_seconds FROM episodes WHERE episode_number = ?",
            (episode_number,),
        ).fetchone()

    # Bucket frames into time windows
    max_time = frames[-1]["time_seconds"]
    num_buckets = int(max_time / bucket_seconds) + 1
    buckets = [0.0] * num_buckets

    for f in frames:
        idx = int(f["time_seconds"] / bucket_seconds)
        if idx < num_buckets:
            buckets[idx] = max(buckets[idx], f["score"])

    timeline = [
        {"t": round(i * bucket_seconds, 1), "v": round(buckets[i], 3)}
        for i in range(num_buckets)
    ]

    set_markers = [
        {
            "set_id": s["set_id"],
            "set_number": s["set_number"],
            "comedian_name": s["comedian_name"],
            "start": s["set_start_seconds"],
            "end": s["set_end_seconds"],
            "status": s["status"],
        }
        for s in sets
        if s["set_start_seconds"] is not None
    ]

    return {
        "episode_number": episode_number,
        "bucket_seconds": bucket_seconds,
        "total_laughter_seconds": ep["total_laughter_seconds"] if ep else None,
        "timeline": timeline,
        "sets": set_markers,
    }


def get_crowd_reaction_distribution(db_path: Path) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT crowd_reaction, COUNT(*) AS count
            FROM sets
            WHERE crowd_reaction IS NOT NULL
            GROUP BY crowd_reaction
            ORDER BY count DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]
