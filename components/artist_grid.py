from dash import html


def render_artist_card(artist: dict, rank: int) -> html.Div:
    image_url = artist.get("image_url")
    name = artist.get("name") or ""
    children = []
    if image_url:
        class_name = "artist-card"
        style = {"backgroundImage": f"url({image_url})"}
    else:
        # No image (demo data or an expired Spotify CDN URL): render an
        # intentional placeholder tile with the artist's initial instead
        # of a bare dark box.
        class_name = "artist-card artist-card--placeholder"
        style = {}
        initial = name[0].upper() if name else "?"
        children.append(
            html.Span(initial, className="artist-card__initial")
        )
    children.append(
        html.Div(
            className="artist-card__overlay",
            children=[
                html.Span(f"#{rank}", className="artist-card__rank"),
                html.Span(name, className="artist-card__name"),
            ],
        )
    )
    return html.Div(className=class_name, style=style, children=children)


def render_grid(artists: list[dict]) -> html.Div:
    return html.Div(
        className="artist-grid",
        children=[render_artist_card(a, a["rank"]) for a in artists],
    )
