import pathlib

import pytest

from kupala.config import Secrets


def test_secrets(tmp_path: pathlib.Path) -> None:
    secret_file = tmp_path / "value.secret"
    secret_file.write_text("1")

    secrets = Secrets(tmp_path)

    assert secrets.get("value.secret") == "1"
    assert secrets.get("missing.secret", "default") == "default"
    assert secrets.get("value.secret", cast=int) == 1

    with pytest.raises(FileNotFoundError, match="Secret file missing"):
        secrets.get("missing.secret")
