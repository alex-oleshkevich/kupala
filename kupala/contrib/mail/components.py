import abc
import jinja2
import typing

default_env = jinja2.Environment(loader=jinja2.PackageLoader("kupala.contrib.mail"))


class MailComponent(abc.ABC):
    @abc.abstractmethod
    def render(self) -> str:
        ...

    def __str__(self) -> str:
        return self.render()


class TemplatedMailComponent(MailComponent):
    jinja_env: jinja2.Environment = default_env

    @classmethod
    def bind_jinja_environment(cls, jinja_env: jinja2.Environment) -> None:
        cls.jinja_env = jinja_env

    def render_template(self, template_name: str, context: dict[str, typing.Any]) -> str:
        template = self.jinja_env.get_template(template_name)
        return template.render(context)


class Envelope(TemplatedMailComponent):
    def __init__(self, body: MailComponent) -> None:
        self.body = body

    def render(self) -> str:
        return self.render_template("kupala/mail/components/envelope.html", {"body": self.body})
