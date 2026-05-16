from dash import dcc
import plotly.graph_objects as go


def render_genre_chart(genres: list[dict]) -> dcc.Graph:
    if not genres:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="#1e1e1e",
            plot_bgcolor="#1e1e1e",
            font_color="#b3b3b3",
            annotations=[{
                "text": "No genre data available",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"color": "#b3b3b3", "size": 14},
            }],
        )
        return dcc.Graph(figure=fig)

    # Reverse so highest count is at top
    sorted_genres = sorted(genres, key=lambda g: g["count"])
    y = [g["genre"] for g in sorted_genres]
    x = [g["count"] for g in sorted_genres]

    fig = go.Figure(go.Bar(
        x=x,
        y=y,
        orientation="h",
        marker_color="#1db954",
        hovertemplate="%{y}: %{x} artists<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#1e1e1e",
        plot_bgcolor="#1e1e1e",
        font_color="#ffffff",
        xaxis=dict(
            title="Number of top artists",
            color="#b3b3b3",
            showgrid=False,
            tickcolor="#b3b3b3",
        ),
        yaxis=dict(
            color="#ffffff",
            showgrid=False,
        ),
        margin=dict(l=16, r=16, t=16, b=40),
    )
    return dcc.Graph(figure=fig)
