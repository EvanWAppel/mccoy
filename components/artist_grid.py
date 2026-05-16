from dash import html


def render_artist_card(artist: dict, rank: int) -> html.Div:
    image_url = artist.get("image_url")
    return html.Div(
        className="artist-card",
        style={"backgroundImage": f"url({image_url})" if image_url else "none"},
        children=[
            html.Div(
                className="artist-card__overlay",
                children=[
                    html.Span(f"#{rank}", className="artist-card__rank"),
                    html.Span(artist["name"], className="artist-card__name"),
                ],
            )
        ],
    )


def render_grid(artists: list[dict]) -> html.Div:
    return html.Div(
        className="artist-grid",
        children=[render_artist_card(a, a["rank"]) for a in artists],
    )
