import pytest

from kupala.exceptions import NotAuthenticatedError
from kupala.responses import TextResponse


def test_no_error_handler(app, test_client):
    def view(request):
        raise TypeError()

    app.routes.get("/", view)
    with pytest.raises(TypeError):
        test_client.get("/")


def test_with_functional_handler(app, test_client):
    def error_handler(request, error):
        return TextResponse("ok")

    def view(request):
        raise TypeError()

    app.routes.get("/", view)
    app.error_handlers.use(TypeError, error_handler)

    response = test_client.get("/")
    assert response.text == "ok"


def test_with_async_functional_handler(app, test_client):
    async def error_handler(request, error):
        return TextResponse("ok")

    def view(request):
        raise TypeError()

    app.routes.get("/", view)
    app.error_handlers.use(TypeError, error_handler)

    response = test_client.get("/")
    assert response.text == "ok"


def test_with_default_http_handler(app, test_client):
    def view(request):
        raise NotAuthenticatedError()

    app.routes.get("/", view)
    response = test_client.get("/")
    assert response.status_code == 401


def test_with_numeric_handler(app, test_client):
    def error_handler(request, error):
        return TextResponse("ok", 401)

    def view(request):
        raise NotAuthenticatedError()

    app.routes.get("/", view)
    app.error_handlers.use(401, error_handler)
    response = test_client.get("/")
    assert response.status_code == 401
    assert response.text == "ok"


def test_with_composite_exception(app, test_client):
    class CompositeError(TypeError):
        ...

    def error_handler(request, error):
        return TextResponse("ok")

    def view(request):
        raise CompositeError()

    app.routes.get("/", view)
    app.error_handlers.use(TypeError, error_handler)
    response = test_client.get("/")
    assert response.text == "ok"
