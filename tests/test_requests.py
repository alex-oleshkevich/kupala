from kupala.requests import CachedBodyMixin, Request, enforce_cached_body


def test_request_is_singleton() -> None:
    enforce_cached_body()
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "headers": [],
    }
    request = Request(scope)
    request2 = Request(scope)
    assert request is request2


def test_cached_body_mixin() -> None:
    class MyRequest(CachedBodyMixin, Request):
        pass

    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "headers": [],
    }
    request = MyRequest(scope)
    request2 = MyRequest(scope)
    assert request is request2
