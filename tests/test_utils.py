import os
import pathlib

from kupala.utils import resolve_path


def test_resolve_path(tmp_path: pathlib.Path) -> None:
    assert os.path.dirname(os.__file__) in resolve_path('@os')
    assert 'kupala/requests' in resolve_path('@kupala/requests')
    assert 'kupala/templates/errors/http_error.html' in resolve_path('@kupala/templates/errors/http_error.html')
    assert __file__ in resolve_path(__file__)

    assert str(tmp_path) in resolve_path(tmp_path)
