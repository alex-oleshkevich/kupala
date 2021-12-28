import os

from kupala.utils import resolve_path


def test_resolve_path() -> None:
    assert os.path.dirname(os.__file__) in resolve_path('os:')
    assert 'kupala/requests' in resolve_path('kupala:requests')
    assert __file__ in resolve_path(__file__)
