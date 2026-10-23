"""Export the dbt marts to a small parquet snapshot (AAA-01).

One file per mart (`<mart>.parquet`, zstd), with the columns and order
of `ask.MARTS_SCHEMA` and arrow types mapped from the Postgres types
named there. The snapshot feeds `analysis/listening.ipynb` (AAA-02),
so the notebook never needs a database connection.

    uv run python -m scripts.export_marts
    uv run python -m scripts.export_marts --out /some/dir

Reads `DATABASE_URL` and opens the session read-only. The default
output, `analysis/data/`, is gitignored: it holds real listening data.
"""

import argparse
import logging
import os
from decimal import Decimal
from pathlib import Path

import psycopg2
import pyarrow as pa
import pyarrow.parquet as pq

import ask

log = logging.getLogger(__name__)

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "analysis" / "data"

# Postgres type (first word of a MARTS_SCHEMA meaning) -> arrow type.
# numeric becomes float64: the marts only hold minutes, and floats are
# what pandas/Hex want for analysis.
ARROW_TYPES: dict[str, pa.DataType] = {
    "text": pa.string(),
    "int": pa.int32(),
    "bigint": pa.int64(),
    "numeric": pa.float64(),
    "date": pa.date32(),
    "timestamp": pa.timestamp("us"),
    "timestamptz": pa.timestamp("us", tz="UTC"),
}


def arrow_type(meaning: str) -> pa.DataType:
    """The arrow type for a MARTS_SCHEMA column meaning ("bigint, ...")."""
    return ARROW_TYPES[meaning.split(",", 1)[0].strip()]


def _schema(mart: str) -> pa.Schema:
    return pa.schema(
        [(col, arrow_type(m)) for col, m in ask.MARTS_SCHEMA[mart]]
    )


def _query(mart: str) -> str:
    columns = [col for col, _ in ask.MARTS_SCHEMA[mart]]
    order = ", ".join(str(i) for i in range(1, len(columns) + 1))
    return (
        f"select {', '.join(columns)} "
        f"from {ask.SCHEMA}.{mart} order by {order}"
    )


def _plain(value):
    return float(value) if isinstance(value, Decimal) else value


def _table(mart: str, rows: list[tuple]) -> pa.Table:
    schema = _schema(mart)
    arrays = [
        pa.array([_plain(row[i]) for row in rows], type=field.type)
        for i, field in enumerate(schema)
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


def export_marts(conn, out_dir: Path | str) -> dict[str, int]:
    """Write every mart to `out_dir/<mart>.parquet`; return row counts."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    conn.set_session(readonly=True)
    counts: dict[str, int] = {}
    for mart in ask.MARTS_SCHEMA:
        with conn.cursor() as cur:
            cur.execute(_query(mart))
            rows = cur.fetchall()
        path = out / f"{mart}.parquet"
        pq.write_table(_table(mart, rows), path, compression="zstd")
        counts[mart] = len(rows)
        log.info("exported %s: %d rows -> %s", mart, len(rows), path)
    return counts


def main(argv: list[str] | None = None) -> dict[str, int]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        return export_marts(conn, args.out)
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
