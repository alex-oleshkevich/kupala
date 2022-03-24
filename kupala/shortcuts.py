from kupala.application import get_current_application


def render_to_string(template_name: str, context: dict = None) -> str:
    app = get_current_application()
    return app.render(template_name, context)
