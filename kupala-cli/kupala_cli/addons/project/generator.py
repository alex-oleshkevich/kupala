from kupala_cli.generators import Context, Generator


class ProjectGenerator(Generator):
    def __init__(self, name: str):
        self.name = name

    def generate(self, context: Context) -> None:
        self.render_templates(context, {})
        # self.copy_file("{{project_name}}.env.sample", ".env")
