# BLOCKED — what I need from Evan

- [ ] 🟡 **Screenshots for the README** (primer task 3) — open https://web-production-bee9a.up.railway.app logged out, capture Stats, Trends, Rustle sandbox, and Network; save as PNGs under `docs/screenshots/` and tell Claude to embed them (replaces the "Coming soon" block in `README.md`). Logged-out views only, so no private data.
- [ ] 🟡 **Record the 60–90s Loom** (primer task 4) — follow `LOOM-GUIDE.md` on the logged-out demo, then paste the unlisted link to Claude to add to README + About.
- [ ] 🟡 **Apply `migrations/003_network.sql` to Railway Postgres** (UU-04) — Railway dashboard → Postgres → enable public networking → `psql "$DATABASE_PUBLIC_URL" -f migrations/003_network.sql` → disable public networking. The app falls back to `graph.json` until then.
- [ ] 🟡 **Set `DISCOGS_TOKEN` on Railway** (UU-05) — generate at https://www.discogs.com/settings/developers, add under the web service → Variables. Only needed for re-running ingest on Railway; free personal rate-limit token.
