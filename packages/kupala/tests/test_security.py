import dataclasses
import inspect
import typing

import pytest
from openapi_spec_validator import OpenAPIV32SpecValidator
from starlette.requests import HTTPConnection
from starlette.testclient import TestClient

import kupala
from kupala.applications import Kupala
from kupala.dependencies import (
    MISSING,
    CompileContext,
    InjectionScope,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    Resolver,
    constant,
)
from kupala.errors import BadRequestError, NotAuthenticatedError
from kupala.responses import Response
from kupala.routing import Routes
from kupala.schema import openapi
from kupala.schema.builder import build_document
from kupala.security import Bearer, Identity
from kupala.testutils import ScopeFactory


def bearer_client(binding: Bearer) -> TestClient:
    routes = Routes()

    @routes.get("/")
    async def endpoint(token: typing.Annotated[str, binding]) -> Response:
        return Response(token)

    return TestClient(Kupala("tests", routes=routes), raise_server_exceptions=False)


def compile_bearer(
    binding: Bearer,
    *,
    type_: typing.Any = str,
    default: object = MISSING,
) -> Resolver:
    return binding.compile(
        CompileContext(),
        ParamInfo(
            name="token",
            type=type_,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=type_,
            default=default,
            metadata=(binding,),
        ),
    )


class TestIdentity:
    def test_preserves_the_principal_and_granted_scopes(self) -> None:
        principal = object()

        identity: Identity[object] = Identity(principal, frozenset({"profile:read"}))

        assert identity.principal is principal
        assert identity.scopes == {"profile:read"}

    def test_defaults_to_no_granted_scopes(self) -> None:
        identity = Identity("alice")

        assert identity.scopes == frozenset()

    def test_is_frozen_and_slotted(self) -> None:
        identity = Identity("alice")

        with pytest.raises(dataclasses.FrozenInstanceError):
            identity.__setattr__("principal", "bob")

        assert not hasattr(identity, "__dict__")

    def test_is_exported_from_the_public_package(self) -> None:
        assert kupala.Identity is Identity


class TestBearer:
    def test_requires_a_realm_for_a_valid_challenge(self) -> None:
        with pytest.raises(TypeError, match="realm"):
            typing.cast(typing.Any, Bearer)()

    @pytest.mark.parametrize(
        ("authorization", "token"),
        [
            ("Bearer token", "token"),
            ("bEaReR   abc._~+/-==", "abc._~+/-=="),
            ("  Bearer padded  ", "padded"),
        ],
    )
    def test_returns_the_exact_token(self, authorization: str, token: str) -> None:
        with bearer_client(Bearer(realm="test")) as client:
            response = client.get("/", headers={"Authorization": authorization})

        assert response.status_code == 200
        assert response.text == token

    @pytest.mark.parametrize("authorization", [None, "Basic token"])
    def test_missing_bearer_credentials_get_a_realm_challenge(self, authorization: str | None) -> None:
        headers = {} if authorization is None else {"Authorization": authorization}

        with bearer_client(Bearer(realm="test")) as client:
            response = client.get("/", headers=headers)

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="test"'

    @pytest.mark.parametrize(
        "authorization",
        [
            "",
            "Bearer",
            "Bearer token value",
            "Bearer to=ken",
            "Bearer\ttoken",
            "Bearer one, Bearer two",
        ],
    )
    def test_malformed_credentials_are_a_bad_request(self, authorization: str) -> None:
        with bearer_client(Bearer(realm="test")) as client:
            response = client.get(
                "/",
                headers={"Authorization": authorization},
            )

        assert response.status_code == 400
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="test", error="invalid_request"'
        assert response.text == "400: Malformed Bearer credentials."

    async def test_rejects_non_ascii_credentials(self, scope_f: ScopeFactory) -> None:
        binding = Bearer(realm="test")
        context = InvocationContext(
            InjectionScope(
                {HTTPConnection: constant(HTTPConnection(scope_f(headers=[(b"authorization", b"Bearer t\xe9st")])))},
            )
        )

        with pytest.raises(BadRequestError, match="Malformed Bearer credentials"):
            await compile_bearer(binding)(context)

    def test_duplicate_authorization_fields_are_a_bad_request(self) -> None:
        with bearer_client(Bearer(realm="test")) as client:
            response = client.get(
                "/",
                headers=[("Authorization", "Bearer one"), ("Authorization", "Bearer two")],
            )

        assert response.status_code == 400
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="test", error="invalid_request"'

    @pytest.mark.parametrize(
        ("realm", "challenge"),
        [
            ('private "area"', 'Bearer realm="private \\"area\\""'),
            ("private\\area", 'Bearer realm="private\\\\area"'),
        ],
    )
    def test_quotes_the_realm_safely(self, realm: str, challenge: str) -> None:
        with bearer_client(Bearer(realm=realm)) as client:
            response = client.get("/")

        assert response.headers["WWW-Authenticate"] == challenge

    @pytest.mark.parametrize("realm", ["line\nbreak", "tab\tseparated", "snowman ☃"])
    def test_rejects_a_realm_that_is_not_printable_ascii(self, realm: str) -> None:
        with pytest.raises(ValueError, match="realm"):
            Bearer(realm=realm)

    @pytest.mark.parametrize("name", ["", "has space", "has/slash"])
    def test_rejects_an_invalid_openapi_component_name(self, name: str) -> None:
        with pytest.raises(ValueError, match="name"):
            Bearer(realm="test", name=name)

    def test_requires_a_non_optional_string_annotation(self) -> None:
        binding = Bearer(realm="test")

        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_bearer(binding, type_=int)
        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_bearer(binding, default=None)

    async def test_caches_extraction_by_binding_identity(self, scope_f: ScopeFactory) -> None:
        binding = Bearer(realm="test")
        context = InvocationContext(
            InjectionScope(
                {HTTPConnection: constant(HTTPConnection(scope_f(headers=[(b"authorization", b"Bearer first")])))},
            )
        )
        resolver = compile_bearer(binding)

        assert await resolver(context) == "first"
        context.scope.bind(
            HTTPConnection,
            constant(HTTPConnection(scope_f(headers=[(b"authorization", b"Bearer second")]))),
        )
        assert await resolver(context) == "first"

    async def test_equal_bindings_and_separate_contexts_do_not_share_tokens(self, scope_f: ScopeFactory) -> None:
        first = Bearer(realm="test")
        second = Bearer(realm="test")
        context = InvocationContext(
            InjectionScope(
                {HTTPConnection: constant(HTTPConnection(scope_f(headers=[(b"authorization", b"Bearer first")])))}
            )
        )

        assert await compile_bearer(first)(context) == "first"
        context.scope.bind(HTTPConnection, constant(HTTPConnection(scope_f(headers=[]))))
        with pytest.raises(NotAuthenticatedError):
            await compile_bearer(second)(context)

        fresh = InvocationContext(InjectionScope({HTTPConnection: constant(HTTPConnection(scope_f(headers=[])))}))
        with pytest.raises(NotAuthenticatedError):
            await compile_bearer(first)(fresh)

    async def test_rejects_websocket_use_explicitly(self, scope_f: ScopeFactory) -> None:
        connection = HTTPConnection(scope_f(type="websocket"))
        context = InvocationContext(InjectionScope({HTTPConnection: constant(connection)}))

        with pytest.raises(InvalidDependencyError, match="HTTP requests"):
            await compile_bearer(Bearer(realm="test"))(context)

    def test_contributes_the_runtime_security_contract_to_openapi(self) -> None:
        binding = Bearer(name="accessToken", bearer_format="JWT", realm="api")
        routes = Routes()

        @routes.get("/private")
        async def endpoint(token: typing.Annotated[str, binding]) -> Response:
            return Response(token)  # pragma: no cover

        document = build_document(
            routes,
            openapi.OpenAPI(info=openapi.Info(title="Test", version="1")),
        )
        rendered = openapi.to_dict(document)
        OpenAPIV32SpecValidator(rendered).validate()

        assert rendered["components"]["securitySchemes"]["accessToken"] == {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        operation = rendered["paths"]["/private"]["get"]
        assert operation["security"] == [{"accessToken": []}]
        assert "parameters" not in operation

    def test_is_exported_from_the_public_package(self) -> None:
        assert kupala.Bearer is Bearer
