import anyio
import click
import functools
import pprint
import typing


class StyledPrinter:
    def print(self, text: str, **format_tokens: typing.Any) -> None:
        click.echo(text.format(**format_tokens))

    def header(self, text: str, **format_tokens: typing.Any) -> None:
        click.secho(text.format(**format_tokens), fg="cyan", bold=True)

    def text(self, text: str, **format_tokens: typing.Any) -> None:
        click.echo(text.format(**format_tokens))

    def success(self, text: str, **format_tokens: typing.Any) -> None:
        click.secho(text.format(**format_tokens), fg="green")

    def error(self, text: str, **format_tokens: typing.Any) -> None:
        click.secho(text.format(**format_tokens), fg="red", bold=True)

    def mark(self, text: str, **format_tokens: typing.Any) -> str:
        return click.style(text.format(**format_tokens), fg="blue")

    def print_variable(self, name: str, value: typing.Any) -> None:
        self.print("{label} = {value}", label=name, value=self.mark(str(value)))

    def dump(self, value: typing.Any) -> None:
        self.print(pprint.pformat(value, indent=4, compact=True))


_PS = typing.ParamSpec("_PS")
_RT = typing.TypeVar("_RT")


def async_command(fn: typing.Callable[_PS, typing.Awaitable[_RT]]) -> typing.Callable[_PS, _RT | None]:
    @functools.wraps(fn)
    def decorator(*args: _PS.args, **kwargs: _PS.kwargs) -> _RT | None:
        async def main() -> _RT:
            return await fn(*args, **kwargs)

        try:
            return anyio.run(main)
        except click.ClickException as ex:
            printer = StyledPrinter()
            printer.error(ex.message)
            return None

    return decorator
