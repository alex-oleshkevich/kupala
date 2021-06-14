import pytest

from kupala.flashes import FlashBag, FlashMessage, Types


@pytest.fixture()
def bag():
    return FlashBag()


def test_add_get(bag):
    bag.error("ERROR")
    bag.success("SUCCESS")
    bag.info("INFO")
    bag.warning("WARNING")
    bag.add("CUSTOM", "custom")

    assert len(bag) == 5
    assert len(bag.all()) == 5

    messages = bag.get()
    assert len(messages) == 5

    errors = bag.get(Types.ERROR)
    assert len(errors) == 1

    errors = bag.get("custom")
    assert len(errors) == 1


def test_bag_callable(bag):
    bag("message", "info")
    assert len(bag) == 1


def test_flush(bag):
    bag.error("ERROR")
    bag.flush()
    assert len(bag) == 0


def test_message_json():
    message = FlashMessage("error", "ERROR")
    assert message.__json__() == {"type": "error", "message": "ERROR"}
