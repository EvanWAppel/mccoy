# DECISIONS

Append-only log of decisions with a real trade-off. Agent drafts; Evan
confirms. Entries marked *(draft)* await confirmation.

## 2026-09-27 — Recruiter expansion scope and order (confirmed)
Chose to build six features in order: Six Degrees → Play-History
Pipeline → Ask Your Listening → Public API → Rec Quality → Analysis.
Six Degrees first because it needs no new infra or credentials.

## 2026-09-27 — Pipeline: dbt-core + Postgres (confirmed)
Chose dbt-core on the existing Postgres, run from a Railway cron.
Rejected Dagster + dbt (stronger signal for Dagster roles, but a heavier
always-on service to host) and plain SQL views (least signal).

## 2026-09-27 — LLM access: owner-live, public-cached (confirmed)
Live Claude calls only for the logged-in owner; visitors see curated
pre-computed answers. Rejected public-live-with-cap (spend exposure +
guardrail overhead) and owner-only (invisible to recruiters).

## 2026-09-27 — API in the Dash Flask server (confirmed)
Chose `/api/v1/*` on the existing server with a hand-written OpenAPI
spec. Rejected a separate FastAPI service (auto-docs, but a second
deploy to keep in sync).

## 2026-09-27 — Analysis in Jupyter, then Hex (confirmed)
Notebook in repo first (agent can build it end to end); Evan ports to
Hex for the Hex CE role.

## 2026-09-27 — Rec quality: keep rate and 4+ rate, separately (confirmed)

## 2026-09-27 — Six Degrees path semantics *(draft)*
Fewest hops (BFS), ties broken by strongest chain (max min-weight, then
max total weight); search the full graph, not the filtered view. Pure
Python, no networkx. Rejected weighted-shortest-path as the default
(less intuitive "degrees") and adding networkx (unneeded at ~240 nodes;
revisit if centrality/communities land in v2).
