import base64
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
from kupala.errors import BadRequestError, InvalidCredentialsError, NotAuthenticatedError, NotAuthorizedError
from kupala.params import QueryParam
from kupala.responses import Response
from kupala.routing import Routes
from kupala.schema import openapi
from kupala.schema.builder import build_document
from kupala.security import APIKey, BasicAuth, BasicCredentials, Bearer, Identity, OAuth2
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


def compile_oauth2(
    binding: OAuth2[typing.Any],
    *,
    type_: typing.Any = str,
    default: object = MISSING,
) -> Resolver:
    return binding.compile(
        CompileContext(),
        ParamInfo(
            name="identity",
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


def basic_client(binding: BasicAuth[typing.Any]) -> TestClient:
    routes = Routes()

    @routes.get("/")
    async def endpoint(credentials: typing.Annotated[BasicCredentials, binding]) -> Response:
        return Response(f"{credentials.username}\0{credentials.password}")

    return TestClient(Kupala("tests", routes=routes), raise_server_exceptions=False)


def compile_basic(
    binding: BasicAuth[typing.Any],
    *,
    type_: typing.Any = BasicCredentials,
    default: object = MISSING,
) -> Resolver:
    return binding.compile(
        CompileContext(),
        ParamInfo(
            name="credentials",
            type=type_,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=type_,
            default=default,
            metadata=(binding,),
        ),
    )


def api_key_client(binding: APIKey[typing.Any]) -> TestClient:
    routes = Routes()

    @routes.get("/")
    async def endpoint(key: typing.Annotated[str, binding]) -> Response:
        return Response(key)

    return TestClient(Kupala("tests", routes=routes), raise_server_exceptions=False)


def compile_api_key(
    binding: APIKey[typing.Any],
    *,
    type_: typing.Any = str,
    default: object = MISSING,
) -> Resolver:
    return binding.compile(
        CompileContext(),
        ParamInfo(
            name="key",
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


class TestBasicCredentials:
    def test_preserves_values_without_exposing_the_password(self) -> None:
        credentials = BasicCredentials("alice", "secret")

        assert credentials.username == "alice"
        assert credentials.password == "secret"
        assert "secret" not in repr(credentials)

    def test_is_frozen_and_slotted(self) -> None:
        credentials = BasicCredentials("alice", "secret")

        with pytest.raises(dataclasses.FrozenInstanceError):
            credentials.__setattr__("username", "bob")

        assert not hasattr(credentials, "__dict__")


class TestBasicAuth:
    @pytest.mark.parametrize(
        ("username", "password"),
        [
            ("alice", "secret"),
            ("Jöhn", "påssword"),
            ("alice", "one:two"),
            ("", "secret"),
            ("alice", ""),
            (" spaced ", " padded "),
        ],
    )
    def test_returns_decoded_credentials(self, username: str, password: str) -> None:
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()

        with basic_client(BasicAuth(realm="test")) as client:
            response = client.get("/", headers={"Authorization": f"bAsIc   {encoded}"})

        assert response.status_code == 200
        assert response.text == f"{username}\0{password}"

    @pytest.mark.parametrize("authorization", [None, "Bearer token"])
    def test_missing_credentials_get_a_basic_challenge(self, authorization: str | None) -> None:
        headers = {} if authorization is None else {"Authorization": authorization}

        with basic_client(BasicAuth(realm="test")) as client:
            response = client.get("/", headers=headers)

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Basic realm="test", charset="UTF-8"'

    @pytest.mark.parametrize(
        "authorization",
        [
            "",
            "Basic",
            "Basic\tdXNlcjpwYXNz",
            "Basic\t dXNlcjpwYXNz",
            "Basic dXNlcjpwYXNz extra",
            "Basic dXNlcjpwYXNz_",
            "Basic dXNlcjpwYQ",
            "Basic dXNlcjpwYXNz===",
            "Basic dXNlcg==",
            "Basic /zpwYXNz",
            f"Basic {base64.b64encode(b'user:\x00pass').decode()}",
        ],
    )
    def test_rejects_malformed_credentials(self, authorization: str) -> None:
        with basic_client(BasicAuth(realm="test")) as client:
            response = client.get("/", headers={"Authorization": authorization})

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Basic realm="test", charset="UTF-8"'
        assert response.text == "401: Invalid Basic credentials."

    def test_rejects_duplicate_authorization_fields(self) -> None:
        with basic_client(BasicAuth(realm="test")) as client:
            response = client.get(
                "/",
                headers=[("Authorization", "Basic dXNlcjpwYXNz"), ("Authorization", "Basic dXNlcjpwYXNz")],
            )

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'Basic realm="test", charset="UTF-8"'

    @pytest.mark.parametrize(
        ("realm", "challenge"),
        [
            ('private "area"', 'Basic realm="private \\"area\\"", charset="UTF-8"'),
            ("private\\area", 'Basic realm="private\\\\area", charset="UTF-8"'),
        ],
    )
    def test_quotes_the_realm_safely(self, realm: str, challenge: str) -> None:
        with basic_client(BasicAuth(realm=realm)) as client:
            response = client.get("/")

        assert response.headers["WWW-Authenticate"] == challenge

    @pytest.mark.parametrize("realm", ["line\nbreak", "tab\tseparated", "snowman ☃"])
    def test_rejects_a_realm_that_is_not_printable_ascii(self, realm: str) -> None:
        with pytest.raises(ValueError, match="realm"):
            BasicAuth(realm=realm)

    @pytest.mark.parametrize("name", ["", "has space", "has/slash"])
    def test_rejects_an_invalid_openapi_component_name(self, name: str) -> None:
        with pytest.raises(ValueError, match="name"):
            BasicAuth(realm="test", name=name)

    def test_requires_non_optional_basic_credentials(self) -> None:
        binding = BasicAuth(realm="test")

        with pytest.raises(InvalidDependencyError, match="required BasicCredentials"):
            compile_basic(binding, type_=str)
        with pytest.raises(InvalidDependencyError, match="required BasicCredentials"):
            compile_basic(binding, default=None)

    async def test_caches_credentials_by_binding_identity(self, scope_f: ScopeFactory) -> None:
        binding = BasicAuth(realm="test")
        connection = HTTPConnection(scope_f(headers=[(b"authorization", b"Basic dXNlcjpwYXNz")]))
        context = InvocationContext(InjectionScope({HTTPConnection: constant(connection)}))
        resolver = compile_basic(binding)

        first = await resolver(context)
        context.scope.bind(
            HTTPConnection,
            constant(HTTPConnection(scope_f(headers=[(b"authorization", b"Basic Ym9iOnNlY3JldA==")]))),
        )

        assert await resolver(context) is first

    async def test_rejects_websocket_use_explicitly(self, scope_f: ScopeFactory) -> None:
        connection = HTTPConnection(scope_f(type="websocket"))
        context = InvocationContext(InjectionScope({HTTPConnection: constant(connection)}))

        with pytest.raises(InvalidDependencyError, match="HTTP requests"):
            await compile_basic(BasicAuth(realm="test"))(context)

    def test_contributes_the_runtime_security_contract_to_openapi(self) -> None:
        binding = BasicAuth(name="account", realm="test")
        routes = Routes()

        @routes.get("/private")
        async def endpoint(_credentials: typing.Annotated[BasicCredentials, binding]) -> Response:
            return Response()  # pragma: no cover

        rendered = openapi.to_dict(
            build_document(routes, openapi.OpenAPI(info=openapi.Info(title="Test", version="1")))
        )
        OpenAPIV32SpecValidator(rendered).validate()

        assert rendered["components"]["securitySchemes"]["account"] == {
            "type": "http",
            "scheme": "basic",
        }
        assert rendered["paths"]["/private"]["get"]["security"] == [{"account": []}]

    def test_is_exported_from_the_public_package(self) -> None:
        assert kupala.BasicAuth is BasicAuth
        assert kupala.BasicCredentials is BasicCredentials


class TestAuthenticatedBasicAuth:
    def test_authenticates_with_an_injected_dependency_and_challenges_rejection(self) -> None:
        async def authenticate(credentials: BasicCredentials, tenant: Injected[int]) -> Identity[str]:
            if credentials.password != "secret":
                raise InvalidCredentialsError("Wrong username or password.")
            return Identity(f"{tenant}:{credentials.username}")

        binding = BasicAuth[str](realm="test", authenticate=authenticate)
        routes = Routes()

        @routes.get("/")
        async def endpoint(identity: typing.Annotated[Identity[str], binding]) -> Response:
            return Response(identity.principal)

        app = Kupala("tests", routes=routes, bindings={int: constant(42)})
        with TestClient(app) as client:
            accepted = client.get("/", headers={"Authorization": "Basic YWxpY2U6c2VjcmV0"})
            rejected_value = base64.b64encode(b"alice:credential-leak").decode()
            rejected = client.get("/", headers={"Authorization": f"Basic {rejected_value}"})

        assert accepted.status_code == 200
        assert accepted.text == "42:alice"
        assert rejected.status_code == 401
        assert rejected.headers["WWW-Authenticate"] == 'Basic realm="test", charset="UTF-8"'
        assert "credential-leak" not in rejected.text

    def test_requires_the_reserved_credential_parameter_type(self) -> None:
        def authenticate(_credentials: str) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        with pytest.raises(InvalidDependencyError, match="required BasicCredentials"):
            compile_basic(
                BasicAuth[str](realm="test", authenticate=authenticate),
                type_=Identity[str],
            )

    def test_requires_a_parameterized_non_optional_identity_target(self) -> None:
        def authenticate(_credentials: BasicCredentials) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        binding = BasicAuth[str](realm="test", authenticate=authenticate)

        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_basic(binding)
        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_basic(binding, type_=Identity[str], default=None)

    def test_documents_transitive_dependencies_without_the_credentials(self) -> None:
        secondary = Bearer(realm="secondary", name="secondary")

        async def authenticate(
            _credentials: typing.Annotated[BasicCredentials, QueryParam("credentials")],
            tenant: typing.Annotated[str, QueryParam("tenant")],
            _secondary: typing.Annotated[str, secondary],
        ) -> Identity[str]:
            return Identity(tenant)  # pragma: no cover

        primary = BasicAuth[str](realm="primary", name="primary", authenticate=authenticate)
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


class TestOAuth2:
    def test_returns_a_raw_bearer_token(self) -> None:
        flows = openapi.OAuthFlows(
            client_credentials=openapi.OAuthFlow(token_url="https://auth.example/token", scopes={})
        )
        binding = OAuth2(realm="api", flows=flows)
        routes = Routes()

        @routes.get("/")
        async def endpoint(token: typing.Annotated[str, binding]) -> Response:
            return Response(token)

        with TestClient(Kupala("tests", routes=routes), raise_server_exceptions=False) as client:
            accepted = client.get("/", headers={"Authorization": "Bearer access-token"})
            missing = client.get("/")

        assert accepted.status_code == 200
        assert accepted.text == "access-token"
        assert missing.status_code == 401
        assert missing.headers["WWW-Authenticate"] == 'Bearer realm="api"'

    def test_requires_authentication_to_enforce_scopes(self) -> None:
        flows = openapi.OAuthFlows(
            client_credentials=openapi.OAuthFlow(
                token_url="https://auth.example/token",
                scopes={"products:read": "Read products"},
            )
        )

        with pytest.raises(ValueError, match="authenticate"):
            OAuth2(realm="api", flows=flows, required_scopes=("products:read",))

    @pytest.mark.parametrize("scope", ["", "two scopes", 'quote"', "back\\slash", "snowman☃"])
    def test_rejects_an_invalid_required_scope(self, scope: str) -> None:
        flows = openapi.OAuthFlows(
            client_credentials=openapi.OAuthFlow(token_url="https://auth.example/token", scopes={})
        )

        with pytest.raises(ValueError, match="scope"):
            OAuth2[str](
                realm="api",
                flows=flows,
                required_scopes=(scope,),
                authenticate=lambda _token: Identity("user"),
            )

    def test_contributes_flows_and_required_scopes_to_openapi(self) -> None:
        flows = openapi.OAuthFlows(
            authorization_code=openapi.OAuthFlow(
                authorization_url="https://auth.example/authorize",
                token_url="https://auth.example/token",
                scopes={"products:read": "Read products", "products:write": "Modify products"},
            ),
            client_credentials=openapi.OAuthFlow(
                token_url="https://auth.example/token",
                scopes={"products:read": "Read products"},
            ),
        )

        def authenticate(_token: str) -> Identity[str]:
            return Identity("user")  # pragma: no cover

        binding = OAuth2[str](
            realm="api",
            name="productAccess",
            flows=flows,
            required_scopes=("products:write", "products:read", "products:write"),
            authenticate=authenticate,
        )
        routes = Routes()

        @routes.get("/products")
        async def endpoint(_identity: typing.Annotated[Identity[str], binding]) -> Response:
            return Response()  # pragma: no cover

        rendered = openapi.to_dict(
            build_document(routes, openapi.OpenAPI(info=openapi.Info(title="Test", version="1")))
        )
        OpenAPIV32SpecValidator(rendered).validate()

        assert rendered["components"]["securitySchemes"]["productAccess"] == {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://auth.example/authorize",
                    "tokenUrl": "https://auth.example/token",
                    "scopes": {
                        "products:read": "Read products",
                        "products:write": "Modify products",
                    },
                },
                "clientCredentials": {
                    "tokenUrl": "https://auth.example/token",
                    "scopes": {"products:read": "Read products"},
                },
            },
        }
        assert rendered["paths"]["/products"]["get"]["security"] == [
            {"productAccess": ["products:write", "products:read"]}
        ]

    def test_is_exported_from_the_public_package(self) -> None:
        assert kupala.OAuth2 is OAuth2


class TestAuthenticatedOAuth2:
    async def test_returns_an_identity_with_every_required_scope(self, scope_f: ScopeFactory) -> None:
        async def authenticate(token: str, tenant: Injected[int]) -> Identity[str]:
            return Identity(f"{tenant}:{token}", frozenset({"products:read", "products:write"}))

        binding = OAuth2[str](
            realm="api",
            flows=openapi.OAuthFlows(),
            required_scopes=("products:read", "products:write"),
            authenticate=authenticate,
        )
        context = bearer_context(scope_f)
        context.scope.bind(int, constant(42))

        resolved = await compile_oauth2(binding, type_=Identity[str])(context)

        assert resolved == Identity("42:credential", frozenset({"products:read", "products:write"}))

    async def test_accepts_an_identity_with_no_scopes_when_none_are_required(self, scope_f: ScopeFactory) -> None:
        def authenticate(token: str) -> Identity[str]:
            return Identity(token)

        binding = OAuth2[str](realm="api", flows=openapi.OAuthFlows(), authenticate=authenticate)

        assert await compile_oauth2(binding, type_=Identity[str])(bearer_context(scope_f)) == Identity("credential")

    async def test_rejects_an_identity_without_required_scopes(self, scope_f: ScopeFactory) -> None:
        def authenticate(_token: str) -> Identity[str]:
            return Identity("user")

        binding = OAuth2[str](
            realm="private",
            flows=openapi.OAuthFlows(),
            required_scopes=("products:write", "products:read", "products:write"),
            authenticate=authenticate,
        )

        with pytest.raises(NotAuthorizedError, match="required scopes") as caught:
            await compile_oauth2(binding, type_=Identity[str])(bearer_context(scope_f))

        assert caught.value.headers == {
            "WWW-Authenticate": 'Bearer realm="private", error="insufficient_scope", '
            'scope="products:write products:read"'
        }

    async def test_preserves_invalid_token_challenges(self, scope_f: ScopeFactory) -> None:
        def authenticate(_token: str) -> Identity[str]:
            raise InvalidCredentialsError("Do not expose this detail.")

        binding = OAuth2[str](realm="api", flows=openapi.OAuthFlows(), authenticate=authenticate)

        with pytest.raises(InvalidCredentialsError) as caught:
            await compile_oauth2(binding, type_=Identity[str])(bearer_context(scope_f))

        assert caught.value.headers == {"WWW-Authenticate": 'Bearer realm="api", error="invalid_token"'}

    async def test_reuses_the_bearer_result_for_repeated_resolution(self, scope_f: ScopeFactory) -> None:
        calls = 0

        def authenticate(token: str) -> Identity[str]:
            nonlocal calls
            calls += 1
            return Identity(token)

        binding = OAuth2[str](realm="api", flows=openapi.OAuthFlows(), authenticate=authenticate)
        first = compile_oauth2(binding, type_=Identity[str])
        second = compile_oauth2(binding, type_=Identity[str])
        context = bearer_context(scope_f)

        assert await first(context) == Identity("credential")
        assert await second(context) == Identity("credential")
        assert calls == 1

    def test_documents_transitive_authenticator_dependencies(self) -> None:
        async def authenticate(
            _token: typing.Annotated[str, QueryParam("credential")],
            tenant: typing.Annotated[str, QueryParam("tenant")],
        ) -> Identity[str]:
            return Identity(tenant)  # pragma: no cover

        binding = OAuth2[str](
            realm="api",
            flows=openapi.OAuthFlows(),
            name="oauth",
            authenticate=authenticate,
        )
        routes = Routes()

        @routes.get("/private")
        async def endpoint(_identity: typing.Annotated[Identity[str], binding]) -> Response:
            return Response()  # pragma: no cover

        rendered = openapi.to_dict(
            build_document(routes, openapi.OpenAPI(info=openapi.Info(title="Test", version="1")))
        )

        assert [parameter["name"] for parameter in rendered["paths"]["/private"]["get"]["parameters"]] == ["tenant"]


class TestAPIKey:
    def test_reads_a_header_key(self) -> None:
        with api_key_client(APIKey(name="accessKey", key_name="X-API-Key", location="header")) as client:
            response = client.get("/", headers={"X-API-Key": "secret"})

        assert response.status_code == 200
        assert response.text == "secret"

    def test_reads_a_query_key(self) -> None:
        with api_key_client(APIKey(name="accessKey", key_name="api_key", location="query")) as client:
            response = client.get("/", params={"api_key": "secret"})

        assert response.status_code == 200
        assert response.text == "secret"

    def test_reads_a_cookie_key(self) -> None:
        with api_key_client(APIKey(name="accessKey", key_name="session", location="cookie")) as client:
            response = client.get("/", headers={"Cookie": 'other=value; session="secret"'})

        assert response.status_code == 200
        assert response.text == "secret"

    @pytest.mark.parametrize("location", ["header", "query", "cookie"])
    def test_missing_or_empty_key_is_forbidden(self, location: typing.Literal["header", "query", "cookie"]) -> None:
        binding = APIKey(name="accessKey", key_name="api_key", location=location)

        with api_key_client(binding) as client:
            missing = client.get("/")
            if location == "header":
                empty = client.get("/", headers={"api_key": ""})
            elif location == "query":
                empty = client.get("/", params={"api_key": ""})
            else:
                empty = client.get("/", headers={"Cookie": "api_key="})

        assert missing.status_code == 403
        assert empty.status_code == 403
        assert missing.text == "403: API key is required."
        assert empty.text == "403: API key is required."

    def test_rejects_duplicate_header_values(self) -> None:
        binding = APIKey(name="accessKey", key_name="X-API-Key", location="header")

        with api_key_client(binding) as client:
            response = client.get("/", headers=[("X-API-Key", "first"), ("X-API-Key", "second")])

        assert response.status_code == 400
        assert response.text == "400: Multiple API keys were supplied."

    def test_rejects_duplicate_query_values(self) -> None:
        binding = APIKey(name="accessKey", key_name="api_key", location="query")

        with api_key_client(binding) as client:
            response = client.get("/?api_key=first&api_key=second")

        assert response.status_code == 400

    def test_rejects_duplicate_cookie_values(self) -> None:
        binding = APIKey(name="accessKey", key_name="session", location="cookie")

        with api_key_client(binding) as client:
            response = client.get("/", headers={"Cookie": "session=first; session=second"})

        assert response.status_code == 400

    @pytest.mark.parametrize("name", ["", "has space", "has/slash"])
    def test_rejects_an_invalid_openapi_component_name(self, name: str) -> None:
        with pytest.raises(ValueError, match="name"):
            APIKey(name=name, key_name="key", location="header")

    @pytest.mark.parametrize("location", ["body", "path"])
    def test_rejects_an_unsupported_location(self, location: typing.Any) -> None:
        with pytest.raises(ValueError, match="location"):
            APIKey(name="accessKey", key_name="key", location=location)

    @pytest.mark.parametrize(
        ("key_name", "location"),
        [("", "query"), ("line\nbreak", "query"), ("has space", "header"), ("has/slash", "cookie")],
    )
    def test_rejects_an_invalid_wire_name(self, key_name: str, location: typing.Any) -> None:
        with pytest.raises(ValueError, match="key_name"):
            APIKey(name="accessKey", key_name=key_name, location=location)

    def test_requires_a_non_optional_string_annotation(self) -> None:
        binding = APIKey(name="accessKey", key_name="key", location="header")

        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_api_key(binding, type_=int)
        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_api_key(binding, default=None)

    async def test_caches_extraction_by_binding_identity(self, scope_f: ScopeFactory) -> None:
        binding = APIKey(name="accessKey", key_name="key", location="header")
        connection = HTTPConnection(scope_f(headers=[(b"key", b"first")]))
        context = InvocationContext(InjectionScope({HTTPConnection: constant(connection)}))
        resolver = compile_api_key(binding)

        assert await resolver(context) == "first"
        context.scope.bind(
            HTTPConnection,
            constant(HTTPConnection(scope_f(headers=[(b"key", b"second")]))),
        )
        assert await resolver(context) == "first"

    async def test_rejects_websocket_use_explicitly(self, scope_f: ScopeFactory) -> None:
        connection = HTTPConnection(scope_f(type="websocket"))
        context = InvocationContext(InjectionScope({HTTPConnection: constant(connection)}))

        with pytest.raises(InvalidDependencyError, match="HTTP requests"):
            await compile_api_key(APIKey(name="accessKey", key_name="key", location="header"))(context)

    def test_allows_an_explicit_error_policy(self) -> None:
        def authentication_required(_detail: str) -> NotAuthenticatedError:
            return NotAuthenticatedError(headers={"WWW-Authenticate": 'ApiKey realm="test"'})

        binding = APIKey(
            name="accessKey",
            key_name="key",
            location="header",
            error=authentication_required,
        )

        with api_key_client(binding) as client:
            response = client.get("/")

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == 'ApiKey realm="test"'

    @pytest.mark.parametrize("location", ["header", "query", "cookie"])
    def test_contributes_the_runtime_security_contract_to_openapi(
        self,
        location: typing.Literal["header", "query", "cookie"],
    ) -> None:
        binding = APIKey(name="accessKey", key_name="api_key", location=location)
        routes = Routes()

        @routes.get("/private")
        async def endpoint(_key: typing.Annotated[str, binding]) -> Response:
            return Response()  # pragma: no cover

        rendered = openapi.to_dict(
            build_document(routes, openapi.OpenAPI(info=openapi.Info(title="Test", version="1")))
        )
        OpenAPIV32SpecValidator(rendered).validate()

        assert rendered["components"]["securitySchemes"]["accessKey"] == {
            "type": "apiKey",
            "name": "api_key",
            "in": location,
        }
        assert rendered["paths"]["/private"]["get"]["security"] == [{"accessKey": []}]

    def test_is_exported_from_the_public_package(self) -> None:
        assert kupala.APIKey is APIKey


class TestAuthenticatedAPIKey:
    def test_authenticates_with_an_injected_dependency_and_hides_rejection(self) -> None:
        async def authenticate(key: str, tenant: Injected[int]) -> Identity[str]:
            if key != "secret":
                raise InvalidCredentialsError("Rejected credential-leak.")
            return Identity(f"{tenant}:{key}")

        binding = APIKey[str](
            name="accessKey",
            key_name="X-API-Key",
            location="header",
            authenticate=authenticate,
        )
        routes = Routes()

        @routes.get("/")
        async def endpoint(identity: typing.Annotated[Identity[str], binding]) -> Response:
            return Response(identity.principal)

        app = Kupala("tests", routes=routes, bindings={int: constant(42)})
        with TestClient(app) as client:
            accepted = client.get("/", headers={"X-API-Key": "secret"})
            rejected = client.get("/", headers={"X-API-Key": "credential-leak"})

        assert accepted.status_code == 200
        assert accepted.text == "42:secret"
        assert rejected.status_code == 403
        assert "credential-leak" not in rejected.text

    def test_requires_the_reserved_credential_parameter_type(self) -> None:
        def authenticate(_key: int) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        binding = APIKey[str](
            name="accessKey",
            key_name="key",
            location="header",
            authenticate=authenticate,
        )

        with pytest.raises(InvalidDependencyError, match="required str"):
            compile_api_key(binding, type_=Identity[str])

    def test_requires_a_parameterized_non_optional_identity_target(self) -> None:
        def authenticate(_key: str) -> Identity[str]:
            return Identity("unreachable")  # pragma: no cover

        binding = APIKey[str](
            name="accessKey",
            key_name="key",
            location="header",
            authenticate=authenticate,
        )

        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_api_key(binding)
        with pytest.raises(InvalidDependencyError, match=r"Identity\[T\]"):
            compile_api_key(binding, type_=Identity[str], default=None)

    def test_documents_transitive_dependencies_without_the_key(self) -> None:
        secondary = Bearer(realm="secondary", name="secondary")

        async def authenticate(
            _key: typing.Annotated[str, QueryParam("key")],
            tenant: typing.Annotated[str, QueryParam("tenant")],
            _secondary: typing.Annotated[str, secondary],
        ) -> Identity[str]:
            return Identity(tenant)  # pragma: no cover

        primary = APIKey[str](
            name="primary",
            key_name="X-API-Key",
            location="header",
            authenticate=authenticate,
        )
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
            "Bearer\t token",
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
