import pytest

from kupala.config import Config, LockedError


@pytest.fixture()
def config_value():
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
def config(config_value):
    return Config(config_value)


def test_returns_root_node(config, config_value):
    assert type(config.get("application")) == dict


def test_returns_nested_node(config):
    assert config.get("application.debug") is True
    assert type(config.get("application.middleware")) == list


def test_returns_default_when_node_missing(config):
    assert config.get("application.nonexisting", "default") == "default"
    assert config.get("debug", False) is False


def test_raises_when_node_missing_and_no_default(config):
    assert config.get("application.nonexisting") is None


def test_raises_when_node_missing_and_no_default2(config):
    config = Config({"application": {"leaf": []}})
    assert config.get("application.leaf.second") is None


def test_missing_nested_with_default(config):
    assert config.get("application.env", default="prod") == "prod"


def test_returns_dotted_keys(config):
    assert config.get("application.debug", dotpath=False) == "debug"


def test_has_brace_interface(config):
    assert config["application.debug"] is True


def test_merge(config):
    config.merge("app", {"env": "prod"})
    assert config.get("app.env") == "prod"


def test_set_contains_get_del(config):
    config.set("newsection", {"key": "value"})
    assert config.get("newsection.key") == "value"
    del config["newsection"]
    assert "newsection" not in config


def test_set_default(config):
    config.setdefault("a", "test")
    assert config["a"] == "test"


def test_update(config):
    config.update({"new": "key"})
    assert config["new"] == "key"


def test_cant_change_locked_config(config):
    config.lock()
    with pytest.raises(LockedError):
        config.set("newsection", {"key": "value"})

    config.unlock()
    config.set("newsection", {"key": "value"})


def test_temporary_unlock(config):
    config.lock()
    with pytest.raises(LockedError):
        config.set("newsection", {"key": "value"})

    with config.unlock() as config:
        config.set("newsection2", {"key": "value"})

    with pytest.raises(LockedError):
        config.set("newsection3", {"key": "value"})

    assert "newsection2" in config
