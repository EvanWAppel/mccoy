import plotly.graph_objects as go
from dash import dcc


def render_genre_chart(genres: list[dict]) -> dcc.Graph:
    if not genres:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="#eeeadf",
            plot_bgcolor="#eeeadf",
            font_color="#6e6b63",
            annotations=[{
                "text": "No genre data available",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"color": "#6e6b63", "size": 14},
            }],
        )
        return dcc.Graph(figure=fig, className="genre-chart")

    sorted_genres = sorted(genres, key=lambda g: g["count"])
    y = [g["genre"] for g in sorted_genres]
    x = [g["count"] for g in sorted_genres]

    fig = go.Figure(go.Bar(
        x=x,
        y=y,
        orientation="h",
        marker_color="#c4452b",
        hovertemplate="%{y}: %{x} artists<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#eeeadf",
        plot_bgcolor="#eeeadf",
        font_color="#25251f",
        height=520,
        xaxis=dict(
            title="Number of top artists",
            color="#6e6b63",
            showgrid=False,
            tickcolor="#6e6b63",
            dtick=1,
        ),
        yaxis=dict(
            color="#25251f",
            showgrid=False,
            tickfont=dict(size=12),
        ),
        margin=dict(l=16, r=24, t=16, b=48),
    )
    return dcc.Graph(
        figure=fig,
        className="genre-chart",
        config={"displayModeBar": False},
    )
