"""Hourly play-history pipeline: ingest, then dbt build (Group WW).

Run by the Railway cron as ``python pipeline.py``. The dbt project in
analytics/ connects through DBT_* env vars derived from DATABASE_URL.
Each dbt build is recorded in pipeline_runs (job 'dbt_build') with its
model/test counts in ``details``. Failures are recorded and re-raised.
"""

import logging
import os
from contextlib import contextmanager
from pathlib import Path

from dbt.cli.main import dbtRunner
from psycopg2.extensions import parse_dsn

import db
from ingest_plays import run_ingest

logger = logging.getLogger(__name__)

DBT_DIR = Path(__file__).parent / "analytics"


def dbt_env(dsn: str) -> dict[str, str]:
    """DBT_* connection vars for analytics/profiles.yml from a DSN."""
    parts = parse_dsn(dsn)
    return {
        "DBT_HOST": parts.get("host", "localhost"),
        "DBT_PORT": parts.get("port", "5432"),
        "DBT_USER": parts["user"],
        "DBT_PASSWORD": parts.get("password", ""),
        "DBT_DBNAME": parts["dbname"],
    }


@contextmanager
def _env(values: dict[str, str]):
    saved = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_dbt(args: list[str], dsn: str) -> dict:
    """Invoke dbt in-process; return a summary or raise on failure."""
    cli = args + [
        "--project-dir", str(DBT_DIR),
        "--profiles-dir", str(DBT_DIR),
    ]
    logger.info("dbt %s", " ".join(args))
    with _env(dbt_env(dsn)):
        res = dbtRunner().invoke(cli)
    results = list(getattr(res.result, "results", None) or [])
    summary = {
        "status": "success" if res.success else "failed",
        "models_built": sum(
            1 for r in results
            if r.node.resource_type == "model" and r.status == "success"
        ),
        "tests_passed": sum(
            1 for r in results
            if r.node.resource_type == "test" and r.status == "pass"
        ),
        "tests_failed": sum(
            1 for r in results
            if r.node.resource_type == "test"
            and r.status in ("fail", "error")
        ),
    }
    logger.info("dbt %s summary: %s", args[0], summary)
    if not res.success:
        raise RuntimeError(
            f"dbt {args[0]} failed: {res.exception or summary}"
        )
    return summary


def run_pipeline() -> None:
    run_ingest()
    dsn = os.environ["DATABASE_URL"]
    run_id = db.start_pipeline_run("dbt_build")
    try:
        summary = run_dbt(["build"], dsn)
    except Exception as exc:
        db.finish_pipeline_run(run_id, "failed", error=str(exc))
        raise
    db.finish_pipeline_run(run_id, "success", details=summary)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    run_pipeline()
