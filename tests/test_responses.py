import typing
from unittest.mock import Mock

from kupala.requests import Request
from kupala.responses import Response, response


class TestResponseBuilder:
    def test_fluent_methods_clone_and_isolate_state(self) -> None:
        request = typing.cast(Request, Mock())
        builder = response(request)

        authenticated = builder.with_cookie("session", "token")
        logged_out = builder.with_delete_cookie("session")
        overridden = builder.clone(cookies={"override": "value"}, delete_cookies=("old",))
        fluent_clones = (
            builder.with_flash("message", "info"),
            builder.with_vary(),
            builder.with_cache(),
            builder.with_signed_cookie(),
            builder.with_encrypted_cookie(),
        )

        assert authenticated is not builder
        assert logged_out is not builder
        assert overridden is not builder
        assert all(clone is not builder for clone in fluent_clones)

        base_response = builder.text("base", status_code=201, headers={"X-Base": "base"})
        authenticated_response = authenticated.text("authenticated", status_code=201)
        logged_out_response = logged_out.text("logged out", status_code=202)
        overridden_response = overridden.text("overridden")

        assert isinstance(base_response, Response)
        assert base_response.status_code == 201
        assert base_response.headers["X-Base"] == "base"
        assert "set-cookie" not in base_response.headers
        assert authenticated_response.status_code == 201
        assert "session=token" in authenticated_response.headers.getlist("set-cookie")[0]
        assert "session=" in logged_out_response.headers.getlist("set-cookie")[0]
        assert logged_out_response.status_code == 202
        assert "override=value" in overridden_response.headers.getlist("set-cookie")[0]
        assert "old=" in overridden_response.headers.getlist("set-cookie")[1]
