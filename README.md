# mccoy

A personal Spotify listening habits dashboard with a DJ-style
record-flipping playlist builder ("Rustling"). Built in Python with
Plotly Dash, deployed on Railway.

See `prd.md` for the full product spec and `TASKS.md` for
implementation progress.

## Local development

```bash
uv sync
cp .env.example .env  # then fill in Spotify credentials
uv run python app.py
```

## Re-consent on next login

The Rustling feature requires additional Spotify OAuth scopes
beyond what the original dashboard used. The next time you log in
(either locally or in production), Spotify will prompt you to
re-consent and grant the new permissions. This is a one-time prompt
per account.

Current scope set (`auth.SCOPE`):

- `user-top-read`
- `playlist-read-private`
- `playlist-modify-private`
- `playlist-modify-public`
- `streaming`
- `user-read-private`
