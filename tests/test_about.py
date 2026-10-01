"""Group KK — About tab (engineering narrative + recruiter hooks)."""
from datetime import datetime, timezone

from components.about import about_tab, pipeline_health


def _all_text(node):
    return str(node)


class TestAboutTab:
    def test_renders_github_repo_link(self):
        assert "https://github.com/EvanWAppel/mccoy" in _all_text(about_tab())

    def test_renders_linkedin(self):
        assert "linkedin.com/in/evanwebsterappel" in _all_text(about_tab())

    def test_renders_email(self):
        assert "appelew@gmail.com" in _all_text(about_tab())

    def test_renders_resume_link(self):
        assert "/assets/resume.pdf" in _all_text(about_tab())

    def test_has_architecture_section(self):
        text = _all_text(about_tab())
        assert "Architecture" in text or "architecture" in text

    def test_has_build_story(self):
        text = _all_text(about_tab())
        assert "Why" in text or "built" in text

    def test_has_data_pipeline_note(self):
        # Task 7: the scheduled ingest story should be discoverable
        # without reading code, and stay at true (weekly, personal) scale.
        text = _all_text(about_tab()).lower()
        assert "pipeline" in text
        assert "idempotent" in text
        assert "postgres" in text


HEALTH = {
    "last_ingest_status": "success",
    "last_success_at": datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc),
    "runs_7d": 168,
    "successes_7d": 166,
    "dbt": {"models_built": 8, "tests_passed": 19, "tests_failed": 0},
}


class TestPipelineHealth:
    def test_shows_status_and_success_rate(self, component_text):
        text = component_text(pipeline_health(HEALTH, now=NOW))
        assert "166 of 168" in text
        assert "1 hour ago" in text

    def test_shows_dbt_counts(self, component_text):
        text = component_text(pipeline_health(HEALTH, now=NOW))
        assert "8 models" in text and "19 tests passing" in text

    def test_never_shows_play_counts_or_errors(self):
        health = dict(HEALTH, last_ingest_status="failed")
        rendered = str(pipeline_health(health, now=NOW))
        assert "rows" not in rendered.lower()
        assert "plays" not in rendered.lower()

    def test_failed_last_run_is_flagged(self, component_text):
        health = dict(HEALTH, last_ingest_status="failed")
        text = component_text(pipeline_health(health, now=NOW))
        assert "last run failed" in text.lower()

    def test_not_reported_yet(self, component_text):
        text = component_text(pipeline_health(None, now=NOW))
        assert "hasn't reported yet" in text

    def test_about_tab_includes_health(self, component_ids):
        assert "pipeline-health" in component_ids(about_tab(HEALTH))


NOW = datetime(2026, 9, 30, 18, 5, tzinfo=timezone.utc)
