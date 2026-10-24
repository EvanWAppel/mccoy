"""XX-07: the owner "Ask" UI (question box, answer, SQL, table/chart).

Everything runs on the fake model client from conftest. No test makes
a network call or reads an API key, and in this PR the app has no live
client at all: `app.ask_client_factory` is None until the API-key
guardrail clears (BLOCKED.md).

The security pins at the UI layer:
- only the owner reaches the panel or the callback (layout, callback,
  and over HTTP through Dash's callback endpoint);
- model SQL that writes, or touches a non-marts table, never reaches a
  connection, and the only connection is `ask.connect_readonly`;
- errors show fixed copy, never the SQL, exception text or DSN;
- result values render as text, never as HTML/Markdown.
"""

import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dash import dcc, html

os.environ.setdefault("FLASK_SECRET_KEY", "test_secret")

import app as app_module  # noqa: E402
import ask  # noqa: E402
from components import ask as ask_ui  # noqa: E402
from components.rustle import mode_switcher  # noqa: E402

TOKEN = {"access_token": "x"}


def _result(columns, rows, *, truncated=False, sql="SELECT 1"):
    return ask.AskResult(
        question="q",
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )


# --- component: panel -------------------------------------------------


class TestAskPanel:
    def test_has_question_box_submit_and_result(self, component_ids):
        ids = component_ids(ask_ui.ask_panel())
        assert {"ask-question", "ask-submit", "ask-result"} <= ids

    def test_question_box_is_length_capped(self):
        panel = ask_ui.ask_panel()
        (box,) = [
            c for c in _walk(panel) if getattr(c, "id", "") == "ask-question"
        ]
        assert box.maxLength == ask_ui.MAX_QUESTION_CHARS


# --- component: answer ------------------------------------------------


class TestRenderAnswer:
    def test_sql_is_behind_a_disclosure(self, component_ids):
        sql = "SELECT count(*) AS plays FROM marts.fct_plays"
        tree = ask_ui.render_answer(_result(["plays"], [(3,)], sql=sql))
        (details,) = [
            c for c in _walk(tree) if isinstance(c, html.Details)
        ]
        assert details.id == "ask-sql"
        assert not getattr(details, "open", False)
        assert sql in _text(details)

    def test_table_has_header_and_rows(self, component_text):
        tree = ask_ui.render_answer(
            _result(["artist", "plays"], [("Bon Iver", 12), ("Low", 7)])
        )
        (table,) = [c for c in _walk(tree) if isinstance(c, html.Table)]
        assert table.id == "ask-table"
        text = component_text(table)
        for cell in ("artist", "plays", "Bon Iver", "12", "Low", "7"):
            assert cell in text

    def test_single_value_answer(self, component_text):
        tree = ask_ui.render_answer(_result(["plays"], [(3,)]))
        assert "plays: 3" in component_text(tree)

    def test_multi_row_answer_counts_rows(self, component_text):
        tree = ask_ui.render_answer(
            _result(["artist", "plays"], [("a", 1), ("b", 2)])
        )
        assert "2 rows" in component_text(tree)

    def test_empty_result(self, component_text, component_ids):
        tree = ask_ui.render_answer(_result(["plays"], []))
        assert "No rows" in component_text(tree)
        assert "ask-chart" not in component_ids(tree)

    def test_truncation_is_stated(self, component_text):
        tree = ask_ui.render_answer(
            _result(["n"], [(1,), (2,)], truncated=True)
        )
        assert str(ask.ROW_LIMIT) in component_text(tree)

    def test_label_and_number_pairs_get_a_bar_chart(self):
        tree = ask_ui.render_answer(
            _result(
                ["artist", "minutes"],
                [("Bon Iver", Decimal("12.5")), ("Low", 7)],
            )
        )
        (graph,) = [c for c in _walk(tree) if isinstance(c, dcc.Graph)]
        assert graph.id == "ask-chart"
        (bar,) = graph.figure.data
        assert list(bar.x) == ["Bon Iver", "Low"]
        assert list(bar.y) == [12.5, 7]

    @pytest.mark.parametrize(
        "columns, rows",
        [
            (["plays"], [(1,), (2,)]),  # one column
            (["a", "b", "c"], [("x", 1, 2), ("y", 3, 4)]),  # three
            (["artist", "plays"], [("only", 1)]),  # one row
            (["artist", "name"], [("a", "x"), ("b", "y")]),  # no number
            (["artist", "flag"], [("a", True), ("b", False)]),  # bools
            (["artist", "plays"], [(f"a{i}", i) for i in range(60)]),
        ],
    )
    def test_no_chart_for_other_shapes(self, columns, rows, component_ids):
        tree = ask_ui.render_answer(_result(columns, rows))
        assert "ask-chart" not in component_ids(tree)

    def test_values_render_as_text_not_markup(self):
        evil = "<img src=x onerror=alert(1)>"
        tree = ask_ui.render_answer(
            _result(["artist", "plays"], [(evil, 1), ("b", 2)], sql=evil)
        )
        kinds = {type(c) for c in _walk(tree)}
        assert dcc.Markdown not in kinds
        assert html.Iframe not in kinds
        assert evil in _text(tree)  # present only as a plain string
        assert "dangerously_allow_html" not in repr(tree)

    def test_none_renders_as_blank_cell(self, component_text):
        tree = ask_ui.render_answer(_result(["a", "b"], [(None, 1)]))
        assert "None" not in component_text(tree)


# --- owner layout -----------------------------------------------------


@pytest.fixture
def logged_in(mocker):
    """Logged-in session whose Spotify id is set per test."""
    mocker.patch.object(
        app_module, "get_sp_from_session", return_value=MagicMock()
    )
    mocker.patch.object(
        app_module,
        "get_user_profile",
        return_value={"display_name": "E", "avatar_url": None,
                      "user_id": "u"},
    )

    def as_user(user_id):
        session = {"token": TOKEN}
        if user_id is not None:
            session["spotify_user_id"] = user_id
        mocker.patch.object(app_module.flask, "session", session)

    return as_user


class TestModeSwitcherAsk:
    def test_ask_tab_hidden_by_default(self):
        values = [t.value for t in mode_switcher().children]
        assert "ask" not in values

    def test_ask_tab_when_requested(self):
        values = [t.value for t in mode_switcher(show_ask=True).children]
        assert values[-1] == "ask"


class TestOwnerLayout:
    def test_owner_gets_ask_tab_and_panel(
        self, owner_env, logged_in, component_ids
    ):
        logged_in(owner_env)
        tree = app_module.render_page("/")
        ids = component_ids(tree)
        assert {"ask-wrap", "ask-question", "ask-submit"} <= ids
        assert "ask" in _mode_values(tree)

    @pytest.mark.parametrize("user_id", ["intruder", None])
    def test_non_owner_gets_no_ask_panel(
        self, owner_env, logged_in, user_id, component_ids
    ):
        logged_in(user_id)
        tree = app_module.render_page("/")
        ids = component_ids(tree)
        assert "ask-wrap" in ids  # mounted (hidden) so toggles resolve
        assert not {"ask-question", "ask-submit", "ask-result"} & ids
        assert "ask" not in _mode_values(tree)

    def test_owner_unset_gets_no_ask_panel(
        self, logged_in, monkeypatch, component_ids
    ):
        monkeypatch.delenv("OWNER_SPOTIFY_ID", raising=False)
        logged_in("owner_id")
        ids = component_ids(app_module.render_page("/"))
        assert "ask-question" not in ids

    def test_logged_out_gets_no_ask(self, mocker, component_ids):
        mocker.patch.object(app_module.flask, "session", {})
        ids = component_ids(app_module.render_page("/"))
        assert not any(i.startswith("ask-") for i in ids)


class TestModeToggleAsk:
    def test_ask_mode_shows_only_ask_wrap(self):
        *others, ask_wrap = app_module.toggle_mode("ask")
        assert ask_wrap == {"display": "block"}
        assert all(o == {"display": "none"} for o in others)

    def test_other_modes_hide_ask_wrap(self):
        for mode in ("stats", "rustle", "rate", "network"):
            assert app_module.toggle_mode(mode)[-1] == {"display": "none"}


# --- callback ---------------------------------------------------------


@pytest.fixture
def owner_session(owner_env, mocker):
    mocker.patch.object(
        app_module.flask,
        "session",
        {"token": TOKEN, "spotify_user_id": owner_env},
    )


@pytest.fixture
def wired(mocker, fake_model, ask_conn):
    """Owner Ask wired to the fake model and a mock read-only conn.

    The connection is supplied by patching `ask.connect_readonly`, so
    the test also proves the UI uses the read-only factory.
    """
    mocker.patch.object(
        app_module, "ask_client_factory", lambda: fake_model
    )
    readonly = mocker.patch.object(
        ask, "connect_readonly", return_value=ask_conn
    )
    return fake_model, readonly


def _no_db(mocker):
    """Fail the test if anything opens any database connection."""
    for target in (ask, app_module.db):
        mocker.patch.object(
            target.psycopg2, "connect", side_effect=AssertionError("db")
        )


class TestRunAskOwner:
    def test_renders_answer_sql_and_table(
        self, owner_session, wired, component_ids
    ):
        model, readonly = wired
        model.reply = (
            "```sql\nSELECT primary_artist_name AS artist, count(*) AS "
            "plays FROM marts.fct_plays GROUP BY 1\n```"
        )
        tree = app_module.run_ask(1, None, "Who did I play most?")
        assert {"ask-sql", "ask-table", "ask-chart"} <= component_ids(tree)
        assert model.calls[0]["messages"][0]["content"] == (
            "Who did I play most?"
        )
        readonly.assert_called_once_with()

    def test_enter_key_submits(self, owner_session, wired, component_ids):
        tree = app_module.run_ask(None, 1, "q")
        assert "ask-table" in component_ids(tree)

    def test_question_is_stripped(self, owner_session, wired):
        model, _ = wired
        app_module.run_ask(1, None, "  top artists?  ")
        assert model.calls[0]["messages"][0]["content"] == "top artists?"

    @pytest.mark.parametrize("question", [None, "", "   "])
    def test_blank_question_does_nothing(
        self, owner_session, wired, question
    ):
        model, _ = wired
        with pytest.raises(app_module.PreventUpdate):
            app_module.run_ask(1, None, question)
        assert model.calls == []

    def test_overlong_question_is_refused_before_the_model(
        self, owner_session, wired, component_text
    ):
        model, readonly = wired
        long_q = "x" * (ask_ui.MAX_QUESTION_CHARS + 1)
        tree = app_module.run_ask(1, None, long_q)
        assert str(ask_ui.MAX_QUESTION_CHARS) in component_text(tree)
        assert model.calls == []
        readonly.assert_not_called()


class TestRunAskNoLiveClient:
    """This PR ships no live model wiring (API-key guardrail)."""

    def test_factory_is_unset_by_default(self):
        assert app_module.ask_client_factory is None

    def test_owner_sees_off_notice_and_nothing_is_called(
        self, owner_session, mocker, component_text, component_ids
    ):
        live = mocker.patch.object(
            ask, "default_client", side_effect=AssertionError("live")
        )
        spy = mocker.patch.object(ask, "ask")
        _no_db(mocker)
        tree = app_module.run_ask(1, None, "q")
        assert ask_ui.ASK_OFF in component_text(tree)
        assert "ask-table" not in component_ids(tree)
        live.assert_not_called()
        spy.assert_not_called()

    def test_app_never_builds_a_real_client(self):
        """No live client construction anywhere in the UI code."""
        for path in ("app.py", "components/ask.py"):
            text = (Path(__file__).parent.parent / path).read_text()
            assert "default_client" not in text, path
            assert "import anthropic" not in text, path
            assert "anthropic." not in text.lower(), path


class TestRunAskNonOwner:
    @pytest.mark.parametrize(
        "session",
        [
            {},
            {"token": TOKEN},
            {"token": TOKEN, "spotify_user_id": "intruder"},
            {"spotify_user_id": "owner_id"},  # no token: logged out
        ],
    )
    def test_refused_without_model_or_db(
        self, owner_env, wired, mocker, session, component_text
    ):
        model, readonly = wired
        mocker.patch.object(app_module.flask, "session", session)
        spy = mocker.patch.object(ask, "ask")
        tree = app_module.run_ask(1, None, "Who did I play most?")
        assert ask_ui.ASK_PRIVATE in component_text(tree)
        spy.assert_not_called()
        assert model.calls == []
        readonly.assert_not_called()

    def test_owner_unset_refuses_everyone(
        self, wired, mocker, monkeypatch, component_text
    ):
        model, _ = wired
        monkeypatch.delenv("OWNER_SPOTIFY_ID", raising=False)
        mocker.patch.object(
            app_module.flask,
            "session",
            {"token": TOKEN, "spotify_user_id": "owner_id"},
        )
        tree = app_module.run_ask(1, None, "q")
        assert ask_ui.ASK_PRIVATE in component_text(tree)
        assert model.calls == []


class TestRunAskUnsafeSQL:
    @pytest.mark.parametrize(
        "reply",
        [
            "DELETE FROM marts.fct_plays",
            "UPDATE marts.fct_plays SET track_name = 'x'",
            "SELECT 1; DROP TABLE marts.fct_plays",
            "INSERT INTO marts.fct_plays (play_id) VALUES ('x')",
            "WITH d AS (DELETE FROM marts.fct_plays RETURNING *) "
            "SELECT * FROM d",
            "SELECT * INTO marts.copy FROM marts.fct_plays",
            "SELECT * FROM marts.fct_plays FOR UPDATE",
            "SET ROLE postgres",
            "SELECT refresh_token FROM stored_token",
            "SELECT * FROM public.stored_token",
            "SELECT set_config('default_transaction_read_only', "
            "'off', false)",
            "SELECT query_to_xml('select * from stored_token', "
            "true, true, '')",
        ],
    )
    def test_never_reaches_a_connection(
        self, owner_session, wired, mocker, reply, component_text
    ):
        model, readonly = wired
        model.reply = f"```sql\n{reply}\n```"
        _no_db(mocker)
        tree = app_module.run_ask(1, None, "do something bad")
        readonly.assert_not_called()
        text = component_text(tree)
        assert ask_ui.ASK_UNSAFE in text
        assert reply not in text
        assert "stored_token" not in text
        assert "Error" not in text  # no exception class names


class TestRunAskErrorsDoNotLeak:
    SECRET_DSN = "postgresql://mccoy_ask:hunter2@db.internal:5432/x"

    def test_refusal(self, owner_session, wired, component_text):
        model, _ = wired
        model.stop_reason = "refusal"
        text = component_text(app_module.run_ask(1, None, "q"))
        assert ask_ui.ASK_UNUSABLE in text
        assert "refusal" not in text

    def test_db_error_shows_fixed_copy_and_logs(
        self, owner_session, wired, ask_conn, mock_cursor, caplog,
        component_text,
    ):
        mock_cursor.execute.side_effect = [
            None,
            None,
            RuntimeError(
                f'permission denied for table stored_token '
                f'({self.SECRET_DSN})'
            ),
        ]
        caplog.set_level(logging.ERROR, logger="app")
        tree = app_module.run_ask(1, None, "q")
        text = component_text(tree)
        assert ask_ui.ASK_FAILED in text
        for leak in ("hunter2", "stored_token", "RuntimeError",
                     "permission denied", "SELECT"):
            assert leak not in text
            assert leak not in repr(tree)
        # the detail goes to the server log for the owner to debug
        assert "permission denied" in caplog.text
        ask_conn.rollback.assert_called_once()

    def test_missing_ask_database_url(
        self, owner_session, mocker, fake_model, monkeypatch,
        component_text,
    ):
        mocker.patch.object(
            app_module, "ask_client_factory", lambda: fake_model
        )
        monkeypatch.delenv("ASK_DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", self.SECRET_DSN)
        _no_db(mocker)  # no fallback to the read-write app DB
        text = component_text(app_module.run_ask(1, None, "q"))
        assert ask_ui.ASK_FAILED in text
        assert "ASK_DATABASE_URL" not in text
        assert "hunter2" not in text

    def test_model_client_error(
        self, owner_session, mocker, component_text
    ):
        boom = MagicMock()
        boom.messages.create.side_effect = RuntimeError("sk-ant-secret")
        mocker.patch.object(app_module, "ask_client_factory", lambda: boom)
        text = component_text(app_module.run_ask(1, None, "q"))
        assert ask_ui.ASK_FAILED in text
        assert "sk-ant-secret" not in text


# --- over HTTP: Dash's callback endpoint ------------------------------


def _ask_payload(question):
    return {
        "output": "ask-result.children",
        "outputs": {"id": "ask-result", "property": "children"},
        "inputs": [
            {"id": "ask-submit", "property": "n_clicks", "value": 1},
            {"id": "ask-question", "property": "n_submit", "value": None},
        ],
        "state": [
            {"id": "ask-question", "property": "value", "value": question}
        ],
        "changedPropIds": ["ask-submit.n_clicks"],
    }


class TestAskOverHTTP:
    """A forged callback request is still gated server-side."""

    @pytest.fixture
    def post(self, owner_env, wired):
        def send(session):
            client = app_module.server.test_client()
            with client.session_transaction() as sess:
                sess.update(session)
            return client.post(
                "/_dash-update-component",
                data=json.dumps(_ask_payload("Who did I play most?")),
                content_type="application/json",
            )

        return send

    @pytest.mark.parametrize(
        "session",
        [{}, {"token": TOKEN, "spotify_user_id": "intruder"}],
    )
    def test_non_owner_request_is_refused(self, post, wired, session):
        model, readonly = wired
        resp = post(session)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert ask_ui.ASK_PRIVATE in body
        assert "ask-table" not in body
        assert model.calls == []
        readonly.assert_not_called()

    def test_owner_request_answers(self, post, wired):
        model, readonly = wired
        resp = post({"token": TOKEN, "spotify_user_id": "owner_id"})
        assert resp.status_code == 200
        assert "ask-table" in resp.get_data(as_text=True)
        assert len(model.calls) == 1
        readonly.assert_called_once_with()


# --- helpers ----------------------------------------------------------


def _walk(node):
    if node is None or isinstance(node, (str, int, float)):
        return
    if isinstance(node, (list, tuple)):
        for child in node:
            yield from _walk(child)
        return
    yield node
    yield from _walk(getattr(node, "children", None))


def _text(node):
    parts = []
    for c in _walk(node):
        kids = getattr(c, "children", None)
        kids = kids if isinstance(kids, (list, tuple)) else [kids]
        parts.extend(str(k) for k in kids if isinstance(k, str))
    return " ".join(parts)


def _mode_values(tree):
    (tabs,) = [c for c in _walk(tree) if getattr(c, "id", "") == "mode-tabs"]
    return [t.value for t in tabs.children]
