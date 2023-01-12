import io
import pytest

from kupala.console import StyledPrinter


@pytest.fixture
def file() -> io.StringIO:
    return io.StringIO()


@pytest.fixture
def printer(file: io.StringIO) -> StyledPrinter:
    return StyledPrinter(file=file)


def test_print(printer: StyledPrinter, file: io.StringIO) -> None:
    printer.print("test")
    assert file.getvalue() == "test\n"


def test_header(printer: StyledPrinter, file: io.StringIO) -> None:
    printer.header("test {hello}", hello="world")
    assert file.getvalue() == "test world\n"


def test_text(printer: StyledPrinter, file: io.StringIO) -> None:
    printer.text("test {hello}", hello="world")
    assert file.getvalue() == "test world\n"


def test_success(printer: StyledPrinter, file: io.StringIO) -> None:
    printer.success("test {hello}", hello="world")
    assert file.getvalue() == "test world\n"


def test_error(printer: StyledPrinter, file: io.StringIO) -> None:
    printer.error("test {hello}", hello="world")
    assert file.getvalue() == "test world\n"


def test_dump(printer: StyledPrinter, file: io.StringIO) -> None:
    printer.dump({"a": 1})
    assert file.getvalue() == "{'a': 1}\n"


def test_mark(printer: StyledPrinter, file: io.StringIO) -> None:
    assert printer.mark("test {hello}", hello="world") == "\x1b[34mtest world\x1b[0m"
