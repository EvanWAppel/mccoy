"""Regenerate the public Ask cache (XX-08). Owner-run; costs one model
call per curated question.

    uv run python -m scripts.refresh_ask_cache
    uv run python -m scripts.refresh_ask_cache --model claude-opus-5

Needs ANTHROPIC_API_KEY (the dedicated mccoy workspace key) and
TEST_DATABASE_URL: the fixture marts are loaded into a throwaway
database there, so the cached answers never hold real listening
data. Review the SQL in ask/public_cache.json, then commit it.
"""

import argparse
import logging

import ask
from ask import public
from ask.evals import default_client, fixture_database

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=ask.DEFAULT_MODEL)
    args = parser.parse_args(argv)
    questions = public.load_questions()
    client = default_client()
    with fixture_database() as connect:
        entries = public.refresh_cache(
            questions,
            client=client,
            connect=connect,
            model=args.model,
            path=public.CACHE_PATH,
        )
    for entry in entries:
        print(f"{entry['question']}\n  {entry['sql']}\n")
    print(f"wrote {len(entries)} answers to {public.CACHE_PATH}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
