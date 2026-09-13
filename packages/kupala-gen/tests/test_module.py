import pathlib

import pytest
from click.testing import CliRunner

from kupala_gen.generators.module import generator


def create_project(root: pathlib.Path, *, routes_in_app: bool = False, src: bool = False) -> pathlib.Path:
    package = root / "src" / "demo" if src else root / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"

[project.entry-points."kupala.app"]
app = "demo.app:app"
"""
    )
    routes = "from kupala.routing import Routes\n\nroutes = Routes()\n"
    if routes_in_app:
        (package / "app.py").write_text(routes)
    else:
        (package / "app.py").write_text("from .routes import routes\n")
        (package / "routes.py").write_text(routes)

    return package


class TestModuleGenerator:
    def test_creates_and_registers_a_module(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path)

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (package / "billing/__init__.py").read_text() == ""
        assert (package / "billing/routes.py").read_text() == (
            "from kupala.routing import Routes\n\nroutes = Routes()\n"
        )
        routes = (package / "routes.py").read_text()
        assert "from demo.billing.routes import routes as billing_routes" in routes
        assert "routes = Routes(children=(billing_routes,))" in routes

    def test_discovers_the_project_from_a_child_directory(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        package = create_project(tmp_path / "project")
        monkeypatch.chdir(package)

        result = CliRunner().invoke(generator, ["billing", "--yes"])

        assert result.exit_code == 0
        assert (package / "billing/routes.py").is_file()

    def test_uses_the_workspace_project(self, tmp_path: pathlib.Path) -> None:
        workspace = tmp_path / "workspace"
        project = workspace / "src"
        workspace.mkdir()
        (workspace / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["src"]\n')
        package = create_project(project)

        result = CliRunner().invoke(generator, ["billing", "--project", str(workspace), "--yes"])

        assert result.exit_code == 0
        assert (package / "billing/routes.py").is_file()

    def test_supports_a_src_package(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path, src=True)

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert (package / "billing/routes.py").is_file()

    def test_supports_routes_declared_in_app(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path, routes_in_app=True)

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert "children=(billing_routes,)" in (package / "app.py").read_text()

    def test_rerun_is_unchanged(self, tmp_path: pathlib.Path) -> None:
        create_project(tmp_path)
        runner = CliRunner()

        first = runner.invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])
        second = runner.invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "modified" not in second.output
        assert (tmp_path / "demo/routes.py").read_text().count("demo.billing.routes") == 1

    def test_appends_to_existing_route_children(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path)
        runner = CliRunner()

        first = runner.invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])
        second = runner.invoke(generator, ["users", "--project", str(tmp_path), "--yes"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert "children=(billing_routes, users_routes)" in (package / "routes.py").read_text()

    def test_appends_to_a_children_list(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path)
        routes_file = package / "routes.py"
        routes_file.write_text(
            "from kupala.routing import Routes\n\nadmin_routes = Routes()\nroutes = Routes(children=[admin_routes])\n"
        )

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert "children=[admin_routes, billing_routes]" in routes_file.read_text()

    @pytest.mark.parametrize("name", ["Billing", "class"])
    def test_rejects_an_invalid_module_name(self, tmp_path: pathlib.Path, name: str) -> None:
        create_project(tmp_path)

        result = CliRunner().invoke(generator, [name, "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 2
        assert "snake_case" in result.output
        assert not (tmp_path / "demo" / name).exists()

    def test_rejects_dynamic_children_before_writing(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path)
        routes_file = package / "routes.py"
        original = "from kupala.routing import Routes\n\nchildren = []\nroutes = Routes(children=children)\n"
        routes_file.write_text(original)

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 2
        assert "literal list or tuple" in result.output
        assert routes_file.read_text() == original
        assert not (package / "billing").exists()

    @pytest.mark.parametrize(
        ("source", "message"),
        [
            ("routes = Routes(children=(), children=())\n", "more than one children"),
            ("children = []\nroutes = Routes(children=(*children,))\n", "literal list or tuple"),
            ("routes = factory()\n", "Expected one routes"),
            ("routes = Routes(\n", "Could not parse"),
        ],
    )
    def test_rejects_unsupported_routes_source(self, tmp_path: pathlib.Path, source: str, message: str) -> None:
        package = create_project(tmp_path)
        routes_file = package / "routes.py"
        routes_file.write_text("from kupala.routing import Routes\n\n" + source)

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 2
        assert message in result.output
        assert not (package / "billing").exists()

    @pytest.mark.parametrize(
        ("configuration", "message"),
        [
            (None, "No pyproject.toml"),
            ("not toml =", "Invalid TOML"),
            ('[project]\nname = "demo"\n', "one kupala.app entry point"),
            (
                '[project.entry-points."kupala.app"]\none = "demo.app:app"\ntwo = "demo.app:other"\n',
                "one kupala.app entry point",
            ),
            ('[project.entry-points."kupala.app"]\napp = 1\n', "module:attribute"),
            ('[project.entry-points."kupala.app"]\napp = "demo.app"\n', "module:attribute"),
            ('[project.entry-points."kupala.app"]\napp = "app:app"\n', "inside a package"),
            ('[project.entry-points."kupala.app"]\napp = "missing.app:app"\n', "Could not resolve"),
        ],
    )
    def test_rejects_an_unsupported_project(
        self, tmp_path: pathlib.Path, configuration: str | None, message: str
    ) -> None:
        if configuration is not None:
            (tmp_path / "pyproject.toml").write_text(configuration)

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 2
        assert message in result.output

    def test_requires_a_regular_package(self, tmp_path: pathlib.Path) -> None:
        package = create_project(tmp_path)
        (package / "__init__.py").unlink()

        result = CliRunner().invoke(generator, ["billing", "--project", str(tmp_path), "--yes"])

        assert result.exit_code == 2
        assert "has no __init__.py" in result.output
