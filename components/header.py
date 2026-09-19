from dash import html

from components.editorial import wordmark


def render_header(profile: dict) -> html.Div:
    avatar_url = profile.get("avatar_url")

    avatar = (
        html.Img(
            src=avatar_url, alt="",
            className="app-header__avatar",
        )
        if avatar_url
        else html.Div(
            className="app-header__avatar",
            style={"background": "#333"},
        )
    )

    return html.Div(
        className="app-header",
        children=[
            wordmark(),
            html.Div(
                className="app-header__identity",
                children=[
                    avatar,
                    html.Span(
                        profile.get("display_name", ""),
                        className="app-header__name",
                    ),
                ],
            ),
            html.A("Logout", href="/logout", className="app-header__logout"),
        ],
    )
