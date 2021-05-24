import pytest

from kupala.dotenv import Env


@pytest.fixture()
def example_env(tmp_path, monkeypatch):
    file_path = str(tmp_path / ".env")
    tmp_file = str(tmp_path / ".test_file")
    with open(tmp_file, "w") as f:
        f.write("CONTENTS")

    monkeypatch.setenv("TEST_ENV_VAR", "test_value")
    variables = [
        "BOOLVAL1=yes",
        "BOOLVAL2=y",
        "BOOLVAL3=YES",
        "BOOLVAL4=1",
        "BOOLVAL_NEG1=no",
        "BOOLVAL_NEG2=0",
        "BOOLVAL_NEG3=NO",
        "INTVAL=42",
        "STRVAL=string",
        "BYTESVAL=octet",
        "FLOATVAL=3.14",
        "LISTVAL=example.com, admin.example.com",
        "CSVVAL=id,name,email",
        'JSONVAL={"id": 1, "name": "root"}',
        f"FILEVAL={tmp_file}",
        "PREFIXED_ENV=production",
    ]
    with open(file_path, "w") as f:
        f.write("\n".join(variables))
    return file_path


@pytest.fixture
def env(example_env):
    env = Env()
    env.load(example_env)
    return env


def test_inherits_from_os(env):
    assert env.get("TEST_ENV_VAR") == "test_value"


def test_returns_all(env):
    assert "PATH" in env  # from system vars
    assert "TEST_ENV_VAR" in env
    assert "PREFIXED_ENV" in env


def test_str_cast(env):
    assert env.str("STRVAL") == "string"
    assert env.str("STRVAL_MISSING", default="fallback") == "fallback"


def test_bytes_cast(env):
    assert env.bytes("BYTESVAL") == b"octet"
    assert env.bytes("BYTESVAL_MISSING", default=b"bytes") == b"bytes"


def test_int_cast(env):
    assert env.int("INTVAL") == 42
    assert env.int("INTVAL_MISSING", default=100) == 100


def test_float_cast(env):
    assert env.float("FLOATVAL") == 3.14
    assert env.float("FLOATVAL_MISSING", default=1.0) == 1.0


def test_bool_cast(env):
    assert env.bool("BOOLVAL1") is True
    assert env.bool("BOOLVAL2") is True
    assert env.bool("BOOLVAL3") is True
    assert env.bool("BOOLVAL4") is True
    assert env.bool("BOOLVAL_NEG1") is False
    assert env.bool("BOOLVAL_NEG2") is False
    assert env.bool("BOOLVAL_NEG3") is False

    assert env.bool("BOOLVAL_MISSING", True) is True


def test_list_cast(env, monkeypatch):
    assert env.list("LISTVAL") == ["example.com", "admin.example.com"]

    env.set("LISTVAL_FLOAT", "1.0, 1.1, 1.2")
    assert env.list("LISTVAL_FLOAT", coerce=float) == [1.0, 1.1, 1.2]

    env.set("LISTVAL_SPACE", "example.com admin.example.com")
    assert env.list("LISTVAL_SPACE", split_char=" ") == [
        "example.com",
        "admin.example.com",
    ]

    assert env.list("LISTVAL_MISSING", default=[1, 2, 3]) == [1, 2, 3]


def test_csv_cast(env, monkeypatch):
    assert env.csv("CSVVAL") == ["id", "name", "email"]

    env.set("CSVVAL_FLOAT", "1.0, 1.1, 1.2")
    assert env.csv("CSVVAL_FLOAT", coerce=float) == [1.0, 1.1, 1.2]

    env.set("CSVVAL_SEMICOLON", "a; b; c")
    assert env.csv("CSVVAL_SEMICOLON", delimiter=";") == ["a", "b", "c"]

    assert env.csv("CSVVAL_MISSING", default=[1, 2, 3]) == [1, 2, 3]


def test_json_cast(env, monkeypatch):
    assert env.json("JSONVAL") == {"id": 1, "name": "root"}
    assert env.json("JSONVAL_MISSING", default=[1, 2, 3]) == [1, 2, 3]


def test_file_cast(env, monkeypatch):
    assert env.file("FILEVAL") == "CONTENTS"
    assert env.file("FILEVAL", binary=True) == b"CONTENTS"
    assert env.file("FILEVAL_MISSING", default="FALLBACK") == "FALLBACK"


def test_mapping(env):
    env.set("VAL1", "a")
    env["VAL2"] = "b"

    assert env.get("VAL1") == "a"
    assert env["VAL2"] == "b"

    env.delete("VAL1")
    assert "VAL1" not in env

    del env["VAL2"]
    assert "VAL2" not in env
