from starlette.testclient import TestClient
from unittest import mock

from kupala.applications import Kupala
from kupala.contrib.sentry import SentryExtension


def test_sentry_extension() -> None:
    ext = SentryExtension(
        "http://localhost",
        environment="dev",
        release_id="1",
        sentry_options={"debug": True},
    )
    app = Kupala(extensions=[ext])
    with mock.patch("sentry_sdk.init") as spy:
        with TestClient(app):
            assert spy.call_count == 1
            args = spy.call_args_list[0]
            assert args.args == ("http://localhost",)
            assert args.kwargs["environment"] == "dev"
            assert args.kwargs["release"] == "1"
            assert args.kwargs["debug"] is True
            assert len(args.kwargs["integrations"]) == 1
