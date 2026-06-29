import logging
import os
from pathlib import Path

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cur.execute(path.read_text())
        conn.commit()
    finally:
        conn.close()


def save_refresh_token(token: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stored_token (id, refresh_token, updated_at)
                VALUES (1, %s, now())
                ON CONFLICT (id) DO UPDATE SET refresh_token = EXCLUDED.refresh_token, updated_at = now()
                """,
                (token,),
            )
        conn.commit()
    finally:
        conn.close()


def get_refresh_token() -> str | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT refresh_token FROM stored_token ORDER BY id LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def save_snapshot(time_range: str, artists: list[dict]) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO snapshots (time_range) VALUES (%s) RETURNING id",
                (time_range,),
            )
            snapshot_id = cur.fetchone()[0]
            if artists:
                cur.executemany(
                    """
                    INSERT INTO artist_entries
                        (snapshot_id, rank, artist_name, artist_id, image_url, genres)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            snapshot_id,
                            a["rank"],
                            a["name"],
                            a.get("artist_id", ""),
                            a.get("image_url"),
                            a.get("genres", []),
                        )
                        for a in artists
                    ],
                )
        conn.commit()
        return snapshot_id
    finally:
        conn.close()


def get_snapshots(time_range: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.captured_at, s.time_range,
                       ae.rank, ae.artist_name, ae.artist_id, ae.image_url, ae.genres
                FROM snapshots s
                LEFT JOIN artist_entries ae ON ae.snapshot_id = s.id
                WHERE s.time_range = %s
                ORDER BY s.captured_at, ae.rank
                """,
                (time_range,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    # Group rows by snapshot
    snaps: dict[int, dict] = {}
    for row in rows:
        sid, captured_at, tr, rank, name, artist_id, image_url, genres = row
        if sid not in snaps:
            snaps[sid] = {
                "snapshot_id": sid,
                "captured_at": captured_at,
                "time_range": tr,
                "artists": [],
            }
        if rank is not None:
            snaps[sid]["artists"].append({
                "rank": rank,
                "name": name,
                "artist_id": artist_id,
                "image_url": image_url,
                "genres": genres or [],
            })
    return list(snaps.values())


def get_latest_snapshot(time_range: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.captured_at, s.time_range,
                       ae.rank, ae.artist_name, ae.artist_id,
                       ae.image_url, ae.genres
                FROM snapshots s
                LEFT JOIN artist_entries ae ON ae.snapshot_id = s.id
                WHERE s.id = (
                    SELECT id FROM snapshots
                    WHERE time_range = %s
                    ORDER BY captured_at DESC
                    LIMIT 1
                )
                ORDER BY ae.rank
                """,
                (time_range,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    sid, captured_at, tr = rows[0][0], rows[0][1], rows[0][2]
    snap = {
        "snapshot_id": sid,
        "captured_at": captured_at,
        "time_range": tr,
        "artists": [],
    }
    for row in rows:
        _, _, _, rank, name, artist_id, image_url, genres = row
        if rank is not None:
            snap["artists"].append({
                "rank": rank,
                "name": name,
                "artist_id": artist_id,
                "image_url": image_url,
                "genres": genres or [],
            })
    return snap


def count_snapshots(time_range: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM snapshots WHERE time_range = %s",
                (time_range,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def save_recent_search(user_id: str, query: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO recent_searches (user_id, query, searched_at)
                VALUES (%s, %s, now())
                ON CONFLICT (user_id, query)
                DO UPDATE SET searched_at = now()
                """,
                (user_id, query),
            )
        conn.commit()
    finally:
        conn.close()


def get_recent_searches(user_id: str, limit: int = 5) -> list[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT query
                FROM recent_searches
                WHERE user_id = %s
                ORDER BY searched_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def clear_recent_searches(user_id: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM recent_searches WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()
