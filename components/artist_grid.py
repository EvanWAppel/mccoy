from dash import html


def render_artist_card(artist: dict, rank: int) -> html.Div:
    image_url = artist.get("image_url")
    return html.Div(
        style={
            "position": "relative",
            "aspectRatio": "1",
            "overflow": "hidden",
            "borderRadius": "8px",
            "background": "#1e1e1e",
            "backgroundImage": f"url({image_url})" if image_url else "none",
            "backgroundSize": "cover",
            "backgroundPosition": "center",
        },
        children=[
            html.Div(
                style={
                    "position": "absolute",
                    "bottom": "0",
                    "left": "0",
                    "right": "0",
                    "padding": "8px",
                    "background": "linear-gradient(transparent, rgba(0,0,0,0.85))",
                },
                children=[
                    html.Span(
                        f"#{rank}",
                        style={"color": "#1db954", "fontWeight": "700", "marginRight": "6px"},
                    ),
                    html.Span(
                        artist["name"],
                        style={"color": "#ffffff", "fontWeight": "600", "fontSize": "0.85rem"},
                    ),
                ],
            )
        ],
    )


def render_grid(artists: list[dict]) -> html.Div:
    cards = [render_artist_card(a, a["rank"]) for a in artists]
    return html.Div(
        children=cards,
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(5, 1fr)",
            "gap": "12px",
            "padding": "16px 0",
        },
    )
