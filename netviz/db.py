"""nv_* table access for the music network visualization.

Reuses the root ``db.get_connection`` (same ``DATABASE_URL``) so
connection handling lives in one place. All writes are idempotent so
the ingest job is resumable / re-runnable without duplicating rows.
"""

import logging

from db import get_connection

logger = logging.getLogger(__name__)


def upsert_musician(
    mbid: str,
    name: str,
    discogs_id: str | None = None,
    primary_instrument: str | None = None,
    active_start_year: int | None = None,
    active_end_year: int | None = None,
) -> int:
    """Insert or update a musician (matched on mbid); return its id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nv_musicians
                    (mbid, name, discogs_id, primary_instrument,
                     active_start_year, active_end_year)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (mbid) DO UPDATE SET
                    name = EXCLUDED.name,
                    discogs_id =
                        COALESCE(EXCLUDED.discogs_id, nv_musicians.discogs_id),
                    primary_instrument =
                        COALESCE(EXCLUDED.primary_instrument,
                                 nv_musicians.primary_instrument),
                    active_start_year =
                        COALESCE(EXCLUDED.active_start_year,
                                 nv_musicians.active_start_year),
                    active_end_year =
                        COALESCE(EXCLUDED.active_end_year,
                                 nv_musicians.active_end_year)
                RETURNING id
                """,
                (
                    mbid,
                    name,
                    discogs_id,
                    primary_instrument,
                    active_start_year,
                    active_end_year,
                ),
            )
            musician_id = cur.fetchone()[0]
        conn.commit()
        return musician_id
    finally:
        conn.close()


def upsert_release(
    mbid: str,
    title: str,
    discogs_id: str | None = None,
    year: int | None = None,
    label: str | None = None,
) -> int:
    """Insert or update a release (matched on mbid); return its id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nv_releases
                    (mbid, title, discogs_id, year, label)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (mbid) DO UPDATE SET
                    title = EXCLUDED.title,
                    discogs_id =
                        COALESCE(EXCLUDED.discogs_id, nv_releases.discogs_id),
                    year = COALESCE(EXCLUDED.year, nv_releases.year),
                    label = COALESCE(EXCLUDED.label, nv_releases.label)
                RETURNING id
                """,
                (mbid, title, discogs_id, year, label),
            )
            release_id = cur.fetchone()[0]
        conn.commit()
        return release_id
    finally:
        conn.close()


def upsert_musician_by_discogs(
    discogs_id: str,
    name: str,
    primary_instrument: str | None = None,
) -> int:
    """Insert or update a musician keyed on Discogs id; return its id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nv_musicians
                    (discogs_id, name, primary_instrument)
                VALUES (%s, %s, %s)
                ON CONFLICT (discogs_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    primary_instrument =
                        COALESCE(nv_musicians.primary_instrument,
                                 EXCLUDED.primary_instrument)
                RETURNING id
                """,
                (discogs_id, name, primary_instrument),
            )
            musician_id = cur.fetchone()[0]
        conn.commit()
        return musician_id
    finally:
        conn.close()


def upsert_release_by_discogs(
    discogs_id: str,
    title: str,
    year: int | None = None,
    label: str | None = None,
) -> int:
    """Insert or update a release keyed on Discogs id; return its id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nv_releases (discogs_id, title, year, label)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (discogs_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    year = COALESCE(EXCLUDED.year, nv_releases.year),
                    label = COALESCE(EXCLUDED.label, nv_releases.label)
                RETURNING id
                """,
                (discogs_id, title, year, label),
            )
            release_id = cur.fetchone()[0]
        conn.commit()
        return release_id
    finally:
        conn.close()


def backfill_active_years() -> None:
    """Set each musician's active_start_year to their earliest credit year."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nv_musicians m
                SET active_start_year = sub.first_year
                FROM (
                    SELECT c.musician_id, MIN(r.year) AS first_year
                    FROM nv_credits c
                    JOIN nv_releases r ON r.id = c.release_id
                    WHERE r.year IS NOT NULL
                    GROUP BY c.musician_id
                ) sub
                WHERE m.id = sub.musician_id
                """
            )
        conn.commit()
    finally:
        conn.close()


def add_credit(musician_id: int, release_id: int, role: str | None) -> None:
    """Record that a musician is credited on a release (idempotent)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nv_credits (musician_id, release_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (musician_id, release_id, role) DO NOTHING
                """,
                (musician_id, release_id, role),
            )
        conn.commit()
    finally:
        conn.close()


def replace_edges(edges: list[dict]) -> None:
    """Rebuild nv_edges wholesale from a freshly computed edge list.

    Each edge dict: ``{musician_a, musician_b, weight, sample_releases}``.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM nv_edges")
            if edges:
                cur.executemany(
                    """
                    INSERT INTO nv_edges
                        (musician_a, musician_b, weight, sample_releases)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [
                        (
                            e["musician_a"],
                            e["musician_b"],
                            e["weight"],
                            e.get("sample_releases", []),
                        )
                        for e in edges
                    ],
                )
        conn.commit()
    finally:
        conn.close()


def get_graph() -> dict:
    """Return the whole graph as ``{"nodes": [...], "edges": [...]}``.

    Node: ``{id, name, era, instrument, degree}``.
    Edge: ``{source, target, weight, sample_releases}``.
    Degree is derived from the edge list (no join at render time).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, active_start_year, primary_instrument
                FROM nv_musicians
                """
            )
            musician_rows = cur.fetchall()
            cur.execute(
                """
                SELECT musician_a, musician_b, weight, sample_releases
                FROM nv_edges
                """
            )
            edge_rows = cur.fetchall()
    finally:
        conn.close()

    degree: dict[int, int] = {}
    edges = []
    for a, b, weight, samples in edge_rows:
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
        edges.append(
            {
                "source": a,
                "target": b,
                "weight": weight,
                "sample_releases": samples or [],
            }
        )

    nodes = [
        {
            "id": mid,
            "name": name,
            "era": era,
            "instrument": instrument,
            "degree": degree.get(mid, 0),
        }
        for mid, name, era, instrument in musician_rows
    ]

    return {"nodes": nodes, "edges": edges}
