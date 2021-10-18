import pytest

from kupala.config import Config, LockedError


@pytest.fixture()
def config_value() -> dict:
    return {
        "application.debug": "debug",
        "application": {
            "debug": True,
            "middleware": [
                "middleware_a",
                "middleware_b",
            ],
        },
    }


@pytest.fixture()
def config(config_value: dict) -> Config:
    return Config(config_value)


def test_returns_root_node(config: Config, config_value: dict) -> None:
    assert type(config.get("application")) == dict


def test_returns_nested_node(config: Config) -> None:
    assert config.get("application.debug") is True
    assert type(config.get("application.middleware")) == list


def test_returns_default_when_node_missing(config: Config) -> None:
    assert config.get("application.nonexisting", "default") == "default"
    assert config.get("debug", False) is False


def test_raises_when_node_missing_and_no_default(config: Config) -> None:
    assert config.get("application.nonexisting") is None


def test_raises_when_node_missing_and_no_default2(config: Config) -> None:
    config = Config({"application": {"leaf": []}})
    assert config.get("application.leaf.second") is None


def test_missing_nested_with_default(config: Config) -> None:
    assert config.get("application.env", default="prod") == "prod"


def test_get_key(config: Config) -> None:
    assert config.get_key("application.debug") == "debug"


def test_has_brace_interface(config: Config) -> None:
    assert config["application.debug"] is True


def test_set_contains_get(config: Config) -> None:
    config.set("newsection", {"key": "value"})
    assert config.get("newsection.key") == "value"


def test_update(config: Config) -> None:
    config.update({"new": "key"})
    assert config["new"] == "key"


def test_cant_change_locked_config(config: Config) -> None:
    config.lock()
    with pytest.raises(LockedError):
        config.set("newsection", {"key": "value"})

    config.unlock()
    config.set("newsection", {"key": "value"})


def test_temporary_unlock(config: Config) -> None:
    config.lock()
    with pytest.raises(LockedError):
        config.set("newsection", {"key": "value"})

    with config.unlock() as config:
        config.set("newsection2", {"key": "value"})

    with pytest.raises(LockedError):
        config.set("newsection3", {"key": "value"})
