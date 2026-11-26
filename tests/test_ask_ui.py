"""Ask Your Listening UI (XX-07 owner, XX-08 public cached Q&A).

The owner asks live (model client and DB mocked here). Logged-out
visitors see curated questions answered over the demo/fixture marts,
read from a committed cache; no model call, no real listening data.
"""

import datetime as dt
import json
import os
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("FLASK_SECRET_KEY", "test_secret")

import app as app_module  # noqa: E402
import ask  # noqa: E402
from ask import public  # noqa: E402
from components.ask import (  # noqa: E402
    ask_owner_panel,
    ask_public_panel,
    render_answer,
)
from sql_guard import UnsafeSQLError  # noqa: E402


def answer(columns, rows, **kw):
    base = {
        "question": "Who?",
        "sql": "SELECT 1",
        "columns": columns,
        "rows": rows,
        "truncated": False,
    }
    return {**base, **kw}


TWO_COL = answer(["artist", "plays"], [["Bon Iver", 4], ["Low", 3]])


# --- serialising a result ----------------------------------------------------


def test_normalize_moved_to_ask_and_shared_with_evals():
    from ask import evals

    assert ask.normalize(Decimal("1.50")) == 1.5
    assert ask.normalize(dt.date(2026, 1, 2)) == "2026-01-02"
    assert evals.normalize is ask.normalize


def test_result_dict_is_json_ready():
    result = ask.AskResult(
        question="q",
        sql="SELECT 1",
        columns=["d", "m"],
        rows=[(dt.date(2026, 1, 2), Decimal("3.5"))],
        row_count=1,
        truncated=False,
    )
    d = ask.result_dict(result)
    assert d == answer(["d", "m"], [["2026-01-02", 3.5]], question="q")
    json.dumps(d)


# --- rendering an answer -----------------------------------------------------


def test_answer_shows_table_and_sql(component_ids, component_text):
    tree = render_answer(TWO_COL)
    text = component_text(tree)
    assert "Bon Iver" in text and "artist" in text
    assert "SELECT 1" in text
    assert "ask-table" in str(tree)


def test_sql_sits_in_a_disclosure():
    from dash import html

    tree = render_answer(TWO_COL)
    details = [
        c for c in _walk(tree) if isinstance(c, html.Details)
    ]
    assert details and "SELECT 1" in str(details[0])


def test_label_and_number_get_a_bar_chart(component_ids):
    assert "ask-chart" in component_ids(render_answer(TWO_COL))


@pytest.mark.parametrize(
    "result",
    [
        answer(["plays"], [[12]]),
        answer(["artist", "plays"], [["Low", 3]]),
        answer(["a", "b"], [["x", "y"], ["z", "w"]]),
        answer(["a", "b", "c"], [["x", 1, 2], ["y", 3, 4]]),
    ],
    ids=["one-cell", "one-row", "no-number", "three-cols"],
)
def test_no_chart_when_shape_does_not_fit(result, component_ids):
    assert "ask-chart" not in component_ids(render_answer(result))


def test_single_value_is_the_headline(component_text):
    tree = render_answer(answer(["plays"], [[12]]))
    assert "12" in component_text(tree)
    assert "ask-headline" in str(tree)


def test_empty_result_says_so(component_text):
    tree = render_answer(answer(["plays"], []))
    assert "no rows" in component_text(tree).lower()


def test_long_results_show_first_rows_only(component_text):
    rows = [[f"a{i}", i] for i in range(80)]
    tree = render_answer(answer(["artist", "plays"], rows))
    text = component_text(tree)
    assert "a49" in text and "a50" not in text
    assert "first 50 of 80" in text


def test_truncated_result_mentions_the_cap(component_text):
    tree = render_answer(TWO_COL | {"truncated": True})
    assert str(ask.ROW_LIMIT) in component_text(tree)


# --- panels ------------------------------------------------------------------


def test_owner_panel_has_question_box(component_ids):
    ids = component_ids(ask_owner_panel())
    assert {"ask-question", "ask-submit", "ask-result"} <= ids


def test_public_panel_lists_cached_answers(component_ids, component_text):
    entries = [TWO_COL | {"question": "Top artists?"},
               answer(["plays"], [[3]], question="Sunday plays?")]
    tree = ask_public_panel(entries)
    text = component_text(tree)
    assert "Top artists?" in text and "Sunday plays?" in text
    assert "sample data" in text.lower()
    assert "ask-question" not in component_ids(tree)


def _walk(node):
    from tests.conftest import _walk_components

    return list(_walk_components(node))


# --- curated questions + cache (XX-08) ---------------------------------------


def test_curated_questions_file_is_valid():
    questions = public.load_questions()
    assert 4 <= len(questions) <= 8
    assert len(set(questions)) == len(questions)
    assert all(isinstance(q, str) and q.endswith("?") for q in questions)


def test_load_cache_missing_is_none(tmp_path):
    assert public.load_cache(tmp_path / "nope.json") is None


def test_load_cache_reads_entries(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"model": "m", "entries": [TWO_COL]}))
    assert public.load_cache(path) == [TWO_COL]


def test_refresh_cache_writes_every_answer(tmp_path, ask_conn, fake_model):
    path = tmp_path / "cache.json"
    entries = public.refresh_cache(
        ["Who?", "Who else?"],
        client=fake_model,
        connect=lambda: ask_conn,
        model="claude-test",
        path=path,
    )
    data = json.loads(path.read_text())
    assert data["model"] == "claude-test"
    assert data["data"] == "fixture marts (tests/evals/fixture_marts.sql)"
    assert "generated_at" in data
    assert data["entries"] == entries
    assert [e["question"] for e in entries] == ["Who?", "Who else?"]
    assert entries[0]["rows"] == [["Bon Iver", 12], ["Low", 7]]
    assert {c["model"] for c in fake_model.calls} == {"claude-test"}


def test_refresh_cache_aborts_without_writing_on_unsafe_sql(
    tmp_path, ask_conn, fake_model
):
    fake_model.reply = "DELETE FROM marts.fct_plays"
    path = tmp_path / "cache.json"
    with pytest.raises(UnsafeSQLError):
        public.refresh_cache(
            ["Who?"], client=fake_model, connect=lambda: ask_conn,
            model="m", path=path,
        )
    assert not path.exists()


def test_refresh_script_wires_fixture_db_and_live_client(
    monkeypatch, tmp_path, ask_conn, fake_model
):
    from scripts import refresh_ask_cache

    class Ctx:
        def __enter__(self):
            return lambda: ask_conn

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(refresh_ask_cache, "fixture_database", Ctx)
    monkeypatch.setattr(
        refresh_ask_cache, "default_client", lambda: fake_model
    )
    monkeypatch.setattr(public, "CACHE_PATH", tmp_path / "c.json")
    monkeypatch.setattr(public, "load_questions", lambda: ["Q1?", "Q2?"])
    assert refresh_ask_cache.main(["--model", "claude-test"]) == 0
    data = json.loads((tmp_path / "c.json").read_text())
    assert [e["question"] for e in data["entries"]] == ["Q1?", "Q2?"]


# --- app wiring: public ------------------------------------------------------


class TestPublicAskTab:
    def test_ask_tab_hidden_without_cache(self):
        values = [t.value for t in app_module._public_stats_tabs(2, None)]
        assert "ask" not in values

    def test_ask_tab_shown_with_cache(self):
        tabs = app_module._public_stats_tabs(2, [TWO_COL])
        assert [t.value for t in tabs] == [
            "artists", "trends", "patterns", "ask"
        ]

    def test_toggle_shows_ask(self):
        styles = app_module.toggle_public_content("ask")
        assert styles == (
            {"display": "none"}, {"display": "none"},
            {"display": "none"}, {"display": "block"},
        )

    def test_public_page_never_calls_the_model(self, mocker):
        spy = mocker.patch.object(app_module.ask, "ask")
        mocker.patch.object(
            app_module.ask_public, "load_cache", return_value=[TWO_COL]
        )
        mocker.patch.object(app_module.flask, "session", {})
        tree = app_module.render_page("/")
        ids = {getattr(c, "id", None) for c in _walk(tree)}
        assert {"public-stats-ask", "ask-chart"} <= ids
        spy.assert_not_called()


# --- app wiring: owner -------------------------------------------------------


class TestOwnerAsk:
    @pytest.fixture(autouse=True)
    def owner_session(self, owner_env, mocker):
        mocker.patch.object(
            app_module, "get_sp_from_session", return_value=MagicMock()
        )
        mocker.patch.object(
            app_module.flask, "session", {"spotify_user_id": owner_env}
        )

    def test_owner_layout_has_ask_tab(self, mocker):
        mocker.patch.object(app_module, "get_user_profile",
                            return_value={})
        mocker.patch.object(
            app_module.flask, "session",
            {"spotify_user_id": "owner_id", "token": {"t": 1}},
        )
        tree = app_module.render_page("/")
        values = [getattr(c, "value", None) for c in _walk(tree)]
        assert "ask" in values

    def test_ask_tab_renders_panel(self, component_ids):
        tree = app_module.update_content("short_term", "ask")
        assert "ask-question" in component_ids(tree)

    def test_submit_runs_ask_and_renders(self, mocker, component_ids):
        result = ask.AskResult("Who?", "SELECT 1", ["artist", "plays"],
                               [("Low", 3), ("Bon Iver", 4)], 2, False)
        spy = mocker.patch.object(app_module.ask, "ask", return_value=result)
        tree = app_module.run_ask(1, None, "  Who?  ")
        spy.assert_called_once_with("Who?")
        assert "ask-chart" in component_ids(tree)

    @pytest.mark.parametrize("question", [None, "", "   "])
    def test_blank_question_does_nothing(self, mocker, question):
        from dash.exceptions import PreventUpdate

        spy = mocker.patch.object(app_module.ask, "ask")
        with pytest.raises(PreventUpdate):
            app_module.run_ask(1, None, question)
        spy.assert_not_called()

    def test_guard_block_is_explained(self, mocker, component_text):
        mocker.patch.object(
            app_module.ask, "ask",
            side_effect=UnsafeSQLError("only SELECT is allowed"),
        )
        text = component_text(app_module.run_ask(1, None, "Drop it"))
        assert "blocked" in text.lower()
        assert "only SELECT is allowed" in text

    def test_unusable_reply_is_explained(self, mocker, component_text):
        mocker.patch.object(
            app_module.ask, "ask",
            side_effect=ask.AskError("model declined the question"),
        )
        text = component_text(app_module.run_ask(1, None, "Hm?"))
        assert "model declined the question" in text

    def test_other_errors_shown_and_logged(
        self, mocker, component_text, caplog
    ):
        mocker.patch.object(
            app_module.ask, "ask", side_effect=KeyError("ASK_DATABASE_URL")
        )
        text = component_text(app_module.run_ask(1, None, "Who?"))
        assert "KeyError" in text and "ASK_DATABASE_URL" in text
        assert "ASK_DATABASE_URL" in caplog.text


class TestNonOwnerAsk:
    PRIVATE = "Ask Your Listening is private to the site owner."

    @pytest.fixture(autouse=True)
    def logged_in(self, owner_env, mocker):
        mocker.patch.object(
            app_module, "get_sp_from_session", return_value=MagicMock()
        )
        mocker.patch.object(
            app_module.flask, "session", {"spotify_user_id": "intruder"}
        )

    def test_tab_is_private(self, component_ids):
        tree = app_module.update_content("short_term", "ask")
        assert self.PRIVATE in repr(tree)
        assert "ask-question" not in component_ids(tree)

    def test_submit_never_calls_model(self, mocker):
        spy = mocker.patch.object(app_module.ask, "ask")
        tree = app_module.run_ask(1, None, "Who?")
        assert self.PRIVATE in repr(tree)
        spy.assert_not_called()
