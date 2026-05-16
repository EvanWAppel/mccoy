from dash import html


def render_header(profile: dict) -> html.Div:
    avatar_url = profile.get("avatar_url")
    display_name = profile.get("display_name", "")

    avatar = (
        html.Img(
            src=avatar_url,
            style={
                "width": "36px",
                "height": "36px",
                "borderRadius": "50%",
                "objectFit": "cover",
                "marginRight": "10px",
            },
        )
        if avatar_url
        else html.Div(
            style={
                "width": "36px",
                "height": "36px",
                "borderRadius": "50%",
                "background": "#333",
                "marginRight": "10px",
            }
        )
    )

    return html.Div(
        style={
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "padding": "12px 24px",
            "background": "#1e1e1e",
            "borderBottom": "1px solid #333",
        },
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center"},
                children=[avatar, html.Span(display_name, style={"fontWeight": "600"})],
            ),
            html.A(
                "Logout",
                href="/logout",
                style={
                    "color": "#b3b3b3",
                    "textDecoration": "none",
                    "fontSize": "0.875rem",
                    "border": "1px solid #555",
                    "padding": "4px 12px",
                    "borderRadius": "4px",
                },
            ),
        ],
    )
