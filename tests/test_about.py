"""Group KK — About tab (engineering narrative + recruiter hooks)."""
from components.about import about_tab


def _all_text(node):
    return str(node)


class TestAboutTab:
    def test_renders_github_repo_link(self):
        assert "https://github.com/EvanWAppel/mccoy" in _all_text(about_tab())

    def test_renders_linkedin(self):
        assert "linkedin.com/in/evan-appel-8885569b" in _all_text(about_tab())

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
