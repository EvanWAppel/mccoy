@AGENTS.md
Prime Directive: Do not work if you have any questions or something is not
clear. Ask me for clarification.
Prefer Python
Keep line length less than 80 characters
Use uv
Run Python tools with uv run python
Do not edit pyproject.toml dependencies directly
Use uv add LIB or uv add --dev LIB
Use pytest to implement TDD
Use pytest fixtures in conftest.py to DRY
Use Ruff to lint
Use Ty to typecheck
Use prek for precommits
Use logging to help AI debug
Do not hide or wrap errors
Codex: allowed (self-contained tasks with a test; cross-model review
of high-stakes changes, e.g. the XX-09 Ask security review)

<!-- factotum:blocked-protocol -->
**Blockers → Jira (fleet repo, system standard).** Anything only Evan can resolve — a credential, a deploy, external access, or a decision — becomes a ticket in the Jira `EA` space on *Needs Evan*, component `mccoy`, **with the specific steps a human takes to unblock it** (the action, where, any URL / path / env-var). From a session on Evan's Mac, file it with `uv run --project ~/Documents/_system sys file-blocker --component mccoy --title "…" --body-file steps.md` (add `--nice-to-have` for 🟡; default 🔴); fleet daemon runs on the box park their own ticket on *Needs Evan* instead. Two kinds stay in the root `BLOCKED.md`, in the standard format: **`[sec]` blockers** (`- [ ] 🔴 [sec] …`, because the security dashboard counts them only there, D-052) and anything Jira must not hold — roster/user data, secret values, unpublished writing (D-039). `BLOCKED.md` keeps its heading and a pointer to Jira. _system's blocked-router mirrors both into Evan's todo dashboard. Full rule: Evan's global `~/.claude/CLAUDE.md` and _system D-051/D-052.
<!-- /factotum:blocked-protocol -->
