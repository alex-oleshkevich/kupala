import dataclasses
import inspect
import threading
import typing

import anyio
import pytest
from openapi_spec_validator import OpenAPIV32SpecValidator
from starlette.requests import HTTPConnection
from starlette.testclient import TestClient

import kupala
from kupala.applications import Kupala
from kupala.dependencies import (
    MISSING,
    CircularDependencyError,
    CompileContext,
    Factory,
    Injected,
    InjectionScope,
    InvalidDependencyError,
    InvocationContext,
    ParamInfo,
    Resolver,
    constant,
)
from kupala.errors import BadRequestError, InvalidCredentialsError, NotAuthenticatedError
from kupala.params import QueryParam
from kupala.responses import Response
from kupala.routing import Routes
from kupala.schema import openapi
from kupala.schema.builder import build_document
from kupala.security import Bearer, Identity
from kupala.testutils import ScopeFactory


def bearer_client(binding: Bearer[typing.Any]) -> TestClient:
    routes = Routes()

    @routes.get("/")
    async def endpoint(token: typing.Annotated[str, binding]) -> Response:
        return Response(token)

    return TestClient(Kupala("tests", routes=routes), raise_server_exceptions=False)


def compile_bearer(
    binding: Bearer[typing.Any],
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


def bearer_context(scope_f: ScopeFactory, authorization: bytes = b"Bearer credential") -> InvocationContext:
    connection = HTTPConnection(scope_f(headers=[(b"authorization", authorization)]))
    return InvocationContext(InjectionScope({HTTPConnection: constant(connection)}))


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
    def test_requires_explicit_realm_configuration(self) -> None:
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
        context = bearer_context(scope_f, b"Bearer first")
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


class TestAuthenticatedBearer:
    def test_authenticates_a_route_with_an_async_callback_and_injected_dependencies(self) -> None:
        async def authenticate(
            token: typing.Annotated[str, QueryParam("reserved")],
            tenant: Injected[int],
        ) -> Identity[str]:
            if token == "invalid":
                raise InvalidCredentialsError()
            return Identity(f"{tenant}:{token}", frozenset({"profile:read"}))

        binding = Bearer[str](realm="test", authenticate=authenticate)
        type CurrentIdentity = typing.Annotated[Identity[str], binding]
        routes = Routes()

        @routes.get("/")
        async def endpoint(identity: CurrentIdentity) -> Response:
            assert identity.scopes == {"profile:read"}
            return Response(identity.principal)

        app = Kupala("tests", routes=routes, bindings={int: constant(42)})
        with TestClient(app) as client:
            response = client.get("/", headers={"Authorization": "Bearer credential"})
            rejected = client.get("/", headers={"Authorization": "Bearer invalid"})

        assert response.status_code == 200
        assert response.text == "42:credential"
        assert rejected.status_code == 401
        assert rejected.headers["www-authenticate"] == 'Bearer realm="test", error="invalid_token"'
        assert "invalid" not in rejected.text

    async def test_runs_a_sync_positional_authenticator_in_a_worker_thread(self, scope_f: ScopeFactory) -> None:
        threads: list[int] = []

        def authenticate(token: str, /) -> Identity[int]:
            assert token == "credential"
            threads.append(threading.get_ident())
            return Identity(42)

        binding = Bearer[int](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f)

        identity = await compile_bearer(binding, type_=Identity[int])(context)

        assert identity == Identity(42)
        assert threads and threads[0] != threading.get_ident()

    async def test_caches_the_authenticated_identity_by_binding(self, scope_f: ScopeFactory) -> None:
        calls = 0

        async def authenticate(token: str) -> Identity[str]:
            nonlocal calls
            calls += 1
            return Identity(token)

        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f, b"Bearer first")
        resolver = compile_bearer(binding, type_=Identity[str])

        first = await resolver(context)
        context.scope.bind(
            HTTPConnection,
            constant(HTTPConnection(scope_f(headers=[(b"authorization", b"Bearer second")]))),
        )

        assert await resolver(context) is first
        assert calls == 1

    async def test_attaches_the_bearer_challenge_to_direct_credential_rejection(
        self,
        scope_f: ScopeFactory,
    ) -> None:
        async def authenticate(_token: str) -> Identity[str]:
            raise InvalidCredentialsError(
                "Expired credentials.",
                headers={"X-Authentication": "failed", "www-authenticate": 'Basic realm="wrong"'},
            )

        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f, b"Bearer secret-token")

        with pytest.raises(InvalidCredentialsError, match="Expired credentials") as caught:
            await compile_bearer(binding, type_=Identity[str])(context)

        assert caught.value.headers == {
            "X-Authentication": "failed",
            "WWW-Authenticate": 'Bearer realm="test", error="invalid_token"',
        }
        assert "secret-token" not in str(caught.value)

    async def test_does_not_relabel_rejection_from_an_injected_dependency(self, scope_f: ScopeFactory) -> None:
        async def reject() -> str:
            raise InvalidCredentialsError("Nested rejection.")

        async def authenticate(_token: str, _nested: typing.Annotated[str, Factory(reject)]) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f)

        with pytest.raises(InvalidCredentialsError, match="Nested rejection") as caught:
            await compile_bearer(binding, type_=Identity[str])(context)

        assert caught.value.headers is None

    async def test_preserves_arbitrary_authenticator_errors(self, scope_f: ScopeFactory) -> None:
        async def authenticate(_token: str) -> Identity[str]:
            raise RuntimeError("authentication backend failed")

        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f)

        with pytest.raises(RuntimeError, match="authentication backend failed"):
            await compile_bearer(binding, type_=Identity[str])(context)

    async def test_preserves_authenticator_cancellation(self, scope_f: ScopeFactory) -> None:
        async def authenticate(_token: str) -> Identity[str]:
            await anyio.sleep_forever()
            raise AssertionError  # pragma: no cover

        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f)

        with anyio.move_on_after(0.01) as cancellation:
            await compile_bearer(binding, type_=Identity[str])(context)

        assert cancellation.cancel_called

    def test_requires_a_reserved_credential_parameter(self) -> None:
        def authenticate() -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError, match="first credential parameter"):
            compile_bearer(Bearer[str](realm="test", authenticate=authenticate), type_=Identity[str])

    def test_requires_the_reserved_credential_to_be_a_required_string(self) -> None:
        def wrong_type(_token: int) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        def optional(_token: str = "") -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_bearer(Bearer[str](realm="test", authenticate=wrong_type), type_=Identity[str])
        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_bearer(Bearer[str](realm="test", authenticate=optional), type_=Identity[str])

    def test_requires_a_parameterized_identity_target(self) -> None:
        def authenticate(_token: str) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        binding = Bearer[str](realm="test", authenticate=authenticate)

        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_bearer(binding)
        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_bearer(binding, type_=Identity)
        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_bearer(binding, type_=Identity[str], default=None)

    def test_requires_the_authenticator_return_annotation_to_match_the_target(self) -> None:
        def wrong(_token: str) -> Identity[int]:
            return Identity(1)  # pragma: no cover

        def missing(_token: str):  # type: ignore[no-untyped-def]
            return Identity("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError, match=r"return Identity\[str\]"):
            compile_bearer(Bearer[int](realm="test", authenticate=wrong), type_=Identity[str])
        with pytest.raises(InvalidDependencyError, match=r"return Identity\[str\]"):
            compile_bearer(Bearer[str](realm="test", authenticate=missing), type_=Identity[str])

    def test_accepts_an_alias_for_the_authenticator_return_type(self) -> None:
        type AuthenticatedUser = Identity[str]

        def authenticate(_token: str) -> AuthenticatedUser:
            return Identity("user")  # pragma: no cover

        compile_bearer(Bearer[str](realm="test", authenticate=authenticate), type_=Identity[str])

    async def test_rejects_a_runtime_value_that_is_not_an_identity(self, scope_f: ScopeFactory) -> None:
        async def authenticate(token: str) -> Identity[str]:
            return token  # type: ignore[return-value]

        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f, b"Bearer secret-token")

        with pytest.raises(InvalidDependencyError, match="returned str") as caught:
            await compile_bearer(binding, type_=Identity[str])(context)

        assert "secret-token" not in str(caught.value)

    async def test_bindings_with_different_authenticators_do_not_share_identities(
        self,
        scope_f: ScopeFactory,
    ) -> None:
        async def authenticate_first(_token: str) -> Identity[str]:
            return Identity("first")

        async def authenticate_second(_token: str) -> Identity[str]:
            return Identity("second")

        first = Bearer[str](realm="test", authenticate=authenticate_first)
        second = Bearer[str](realm="test", authenticate=authenticate_second)
        context = bearer_context(scope_f)

        assert await compile_bearer(first, type_=Identity[str])(context) == Identity("first")
        assert await compile_bearer(second, type_=Identity[str])(context) == Identity("second")

    async def test_accepts_an_unhashable_callable_authenticator(self, scope_f: ScopeFactory) -> None:
        @dataclasses.dataclass
        class Authenticate:
            calls: int = 0

            async def __call__(self, token: str) -> Identity[str]:
                self.calls += 1
                return Identity(token)

        authenticate = Authenticate()
        binding = Bearer[str](realm="test", authenticate=authenticate)
        context = bearer_context(scope_f)
        resolver = compile_bearer(binding, type_=Identity[str])

        assert await resolver(context) == Identity("credential")
        assert await resolver(context) == Identity("credential")
        assert authenticate.calls == 1

    def test_detects_a_cycle_between_the_authenticator_and_a_factory(self) -> None:
        def authenticate(
            _token: str,
            nested: typing.Annotated[Identity[str], Factory(authenticate)],
        ) -> Identity[str]:
            return nested  # pragma: no cover

        binding = Bearer[str](realm="test", authenticate=authenticate)

        with pytest.raises(CircularDependencyError, match="Circular dependency"):
            compile_bearer(binding, type_=Identity[str])

    def test_detects_an_authenticator_that_depends_on_its_own_binding(self) -> None:
        def authenticate(
            _token: str,
            nested: typing.Annotated[Identity[str], binding],
        ) -> Identity[str]:
            return nested  # pragma: no cover

        binding = Bearer[str](realm="test", authenticate=authenticate)

        with pytest.raises(CircularDependencyError, match="authenticator cannot depend on itself"):
            compile_bearer(binding, type_=Identity[str])

    def test_documents_transitive_dependencies_but_not_the_reserved_credential(self) -> None:
        secondary = Bearer(realm="secondary", name="secondary")

        async def authenticate(
            _token: typing.Annotated[str, QueryParam("credential")],
            tenant: typing.Annotated[str, QueryParam("tenant")],
            _secondary: typing.Annotated[str, secondary],
        ) -> Identity[str]:
            return Identity(tenant)  # pragma: no cover

        primary = Bearer[str](realm="primary", name="primary", authenticate=authenticate)
        routes = Routes()

        @routes.get("/private")
        async def endpoint(_identity: typing.Annotated[Identity[str], primary]) -> Response:
            return Response()  # pragma: no cover

        rendered = openapi.to_dict(
            build_document(routes, openapi.OpenAPI(info=openapi.Info(title="Test", version="1")))
        )
        OpenAPIV32SpecValidator(rendered).validate()

        operation = rendered["paths"]["/private"]["get"]
        assert [parameter["name"] for parameter in operation["parameters"]] == ["tenant"]
        assert operation["security"] == [{"primary": [], "secondary": []}]
