import logging
import os
from collections import defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

MIGRATION_PATH = Path(__file__).parent / "migrations" / "001_initial.sql"


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    sql = MIGRATION_PATH.read_text()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def save_refresh_token(token: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stored_token (refresh_token, updated_at)
                VALUES (%s, now())
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
            snaps[sid] = {"snapshot_id": sid, "captured_at": captured_at, "artists": []}
        if rank is not None:
            snaps[sid]["artists"].append({
                "rank": rank,
                "name": name,
                "artist_id": artist_id,
                "image_url": image_url,
                "genres": genres or [],
            })
    return list(snaps.values())
