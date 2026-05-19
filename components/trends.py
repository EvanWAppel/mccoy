from collections import defaultdict

import plotly.graph_objects as go
from dash import dcc, html

EMPTY_STATE = html.Div(
    style={"padding": "48px 0", "textAlign": "center"},
    children=[
        html.P(
            "First snapshot captured. Check back next week to see your trends.",
            style={"color": "#b3b3b3", "fontSize": "1rem"},
        ),
    ],
)

DARK_LAYOUT = dict(
    paper_bgcolor="#1e1e1e",
    plot_bgcolor="#1e1e1e",
    font_color="#ffffff",
    margin=dict(l=16, r=24, t=24, b=48),
)


def render_bump_chart(snapshots: list[dict], n: int = 10) -> dcc.Graph | html.Div:
    if len(snapshots) < 2:
        return EMPTY_STATE

    # Collect all unique artist names across snapshots, ranked by best rank seen
    dates = [s["captured_at"] for s in snapshots]

    # Build {artist_name: [rank_or_None per snapshot]}
    artist_ranks: dict[str, list] = defaultdict(lambda: [None] * len(snapshots))
    for i, snap in enumerate(snapshots):
        for a in snap["artists"]:
            artist_ranks[a["name"]][i] = a["rank"]

    # Pick top-N by best (lowest) rank seen across all snapshots
    def best_rank(ranks):
        valid = [r for r in ranks if r is not None]
        return min(valid) if valid else 999

    top_artists = sorted(artist_ranks.keys(), key=lambda name: best_rank(artist_ranks[name]))[:n]

    fig = go.Figure()
    for artist in top_artists:
        ranks = artist_ranks[artist]
        fig.add_trace(go.Scatter(
            x=dates,
            y=ranks,
            mode="lines+markers",
            name=artist,
            line=dict(width=2),
            marker=dict(size=7),
            connectgaps=False,
            hovertemplate=f"<b>{artist}</b><br>%{{x|%b %d}}: #%{{y}}<extra></extra>",
        ))

    fig.update_layout(
        **DARK_LAYOUT,
        height=460,
        yaxis=dict(
            title="Rank",
            autorange="reversed",
            tickmode="linear",
            dtick=1,
            color="#b3b3b3",
            showgrid=False,
        ),
        xaxis=dict(color="#b3b3b3", showgrid=False),
        legend=dict(
            bgcolor="#1e1e1e",
            font=dict(color="#ffffff", size=11),
        ),
        hovermode="x unified",
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def render_area_chart(snapshots: list[dict]) -> dcc.Graph | html.Div:
    if len(snapshots) < 2:
        return EMPTY_STATE

    dates = [s["captured_at"] for s in snapshots]

    # Count genres per snapshot
    genre_counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(snapshots))
    for i, snap in enumerate(snapshots):
        snap_genres: dict[str, int] = defaultdict(int)
        for a in snap["artists"]:
            for g in a.get("genres", []):
                snap_genres[g] += 1
        for genre, count in snap_genres.items():
            genre_counts[genre][i] = count

    # Top 10 genres by total count across all snapshots
    top_genres = sorted(genre_counts.keys(), key=lambda g: sum(genre_counts[g]), reverse=True)[:10]

    fig = go.Figure()
    for genre in top_genres:
        fig.add_trace(go.Scatter(
            x=dates,
            y=genre_counts[genre],
            mode="lines",
            name=genre,
            stackgroup="one",
            hovertemplate=f"<b>{genre}</b>: %{{y}}<extra></extra>",
            line=dict(width=0.5),
        ))

    fig.update_layout(
        **DARK_LAYOUT,
        height=400,
        yaxis=dict(
            title="Artist count",
            color="#b3b3b3",
            showgrid=False,
        ),
        xaxis=dict(color="#b3b3b3", showgrid=False),
        legend=dict(
            bgcolor="#1e1e1e",
            font=dict(color="#ffffff", size=11),
        ),
        hovermode="x unified",
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})
