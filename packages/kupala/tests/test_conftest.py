from kupala.testutils import ScopeFactory


class TestScopeFactory:
    def test_has_common_scope_defaults(self, scope_f: ScopeFactory) -> None:
        scope = scope_f(path="/reports", custom_scope_value="available")

        assert scope == {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/reports",
            "raw_path": b"/reports",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "state": {},
            "extensions": {},
            "subprotocols": [],
            "path_params": {},
            "app": None,
            "router": None,
            "endpoint": None,
            "user": None,
            "session": None,
            "custom_scope_value": "available",
        }
