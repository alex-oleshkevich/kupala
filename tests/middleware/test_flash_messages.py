import pytest
import typing
from starlette.middleware.sessions import SessionMiddleware

from kupala.http import route
from kupala.http.middleware import Middleware
from kupala.http.middleware.flash_messages import (
    FlashBag,
    FlashMessage,
    FlashMessagesMiddleware,
    MessageCategory,
    flash,
)
from kupala.http.requests import Request
from kupala.http.responses import JSONResponse
from tests.conftest import TestClientFactory


@pytest.mark.parametrize("storage", ["session"])
def test_flash_messages(storage: typing.Literal["session"], test_client_factory: TestClientFactory) -> None:
    @route("/set", methods=["post"])
    def set_view(request: Request) -> JSONResponse:
        flash(request).success("This is a message.")
        return JSONResponse({})

    @route("/get")
    def get_view(request: Request) -> JSONResponse:
        bag = flash(request)
        return JSONResponse({"messages": list(bag)})

    client = test_client_factory(
        routes=[set_view, get_view],
        middleware=[
            Middleware(SessionMiddleware, secret_key="key", max_age=80000),
            Middleware(FlashMessagesMiddleware, storage=storage),
        ],
    )
    client.post("/set")

    response = client.get("/get")
    assert response.json()["messages"] == [{"category": "success", "message": "This is a message."}]

    # must be empty after reading messages
    response = client.get("/get")
    assert response.json()["messages"] == []


def test_flash_messages_session_storages_requires_session(test_client_factory: TestClientFactory) -> None:
    client = test_client_factory(middleware=[Middleware(FlashMessagesMiddleware, storage="session")])

    with pytest.raises(KeyError) as ex:
        client.get("/")
    assert ex.value.args[0] == "Sessions are disabled. Flash messages depend on SessionMiddleware."


def test_flash_bag() -> None:
    bag = FlashBag()
    bag.add("success", FlashBag.Category.SUCCESS)
    bag.success("success")
    bag.error("error")
    bag.warning("warning")
    bag.info("info")
    bag.debug("debug")
    assert len(bag) == 6
    assert bool(bag) is True

    bag.clear()
    assert len(bag) == 0
    assert bool(bag) is False


def test_flash_messages_by_category() -> None:
    bag = FlashBag()
    bag.success("one")
    bag.error("two")

    assert bag.get_by_category(MessageCategory.SUCCESS) == [FlashMessage("success", "one")]
    assert len(bag.get_by_category(MessageCategory.SUCCESS)) == 0

    assert bag.get_by_category(MessageCategory.ERROR) == [FlashMessage("error", "two")]
    assert len(bag.get_by_category(MessageCategory.ERROR)) == 0


def test_flash_message() -> None:
    message = FlashMessage("info", "hello")
    assert str(message) == "hello"
