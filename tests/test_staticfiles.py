from pathlib import Path
from starlette.staticfiles import StaticFiles

from kupala.http.routing import Mount
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


def test_staticfiles(test_app_factory: TestAppFactory, tmpdir: Path) -> None:
    asset_name = "main.css"
    asset_path = Path(tmpdir / asset_name)
    asset_path.write_bytes(b"body {}")

    app = test_app_factory(
        routes=[
            Mount("/static", StaticFiles(directory=tmpdir), name="static"),
        ]
    )

    client = TestClient(app)
    response = client.get("/static/" + asset_name)  # test that endpoint created and configured
    assert response.status_code == 200
    assert response.text == "body {}"  # test that static files are served

    # test asset url generation
    assert app.static_url("main.css") == "/static/main.css"
