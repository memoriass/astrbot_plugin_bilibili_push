from .movie_card import MovieCardTheme


class DynamicCardTheme(MovieCardTheme):
    def __init__(
        self,
        renderer,
        template_name="dynamic_movie_card.html.jinja",
        display_timezone="Asia/Shanghai",
    ):
        super().__init__(
            renderer,
            template_name=template_name,
            display_timezone=display_timezone,
        )
