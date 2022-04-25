from kupala.http.responses import JSONResponse


def test_set_cookie_fluent_interface() -> None:
    response = JSONResponse('')
    response = response.set_cookie('key', 'value')
    assert isinstance(response, JSONResponse)
