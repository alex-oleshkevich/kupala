import typing

import pytest

from kupala.api import openapi


class TestCamelize:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("paths", "paths"),
            ("operation_id", "operationId"),
            ("open_id_connect_url", "openIdConnectUrl"),
            # a trailing underscore names a field the specification spells as a Python keyword
            ("in_", "in"),
        ],
    )
    def test_spells_a_field_the_way_the_specification_does(self, name: str, expected: str) -> None:
        assert openapi.camelize(name) == expected


class TestToDict:
    def test_omits_absent_members(self) -> None:
        contact = openapi.Contact(name="Team")

        assert openapi.to_dict(contact) == {"name": "Team"}

    def test_keeps_a_collection_that_is_present_and_empty(self) -> None:
        # `scopes` is required even when a flow defines none, so an empty mapping is not absent
        flow = openapi.OAuthFlow(scopes={}, token_url="/token")

        assert openapi.to_dict(flow) == {"scopes": {}, "tokenUrl": "/token"}

    def test_renders_an_enum_by_value(self) -> None:
        parameter = openapi.Parameter(name="q", in_=openapi.ParameterLocation.QUERY, style=openapi.ParameterStyle.FORM)

        assert openapi.to_dict(parameter) == {"name": "q", "in": "query", "style": "form"}

    def test_aliases_the_reference_key(self) -> None:
        reference = openapi.Reference(ref="#/components/schemas/User", summary="A user")

        assert openapi.to_dict(reference) == {"$ref": "#/components/schemas/User", "summary": "A user"}

    def test_walks_mappings_and_sequences(self) -> None:
        server = openapi.Server(url="/api", variables={"stage": openapi.ServerVariable(default="live")})

        assert openapi.to_dict([server]) == [{"url": "/api", "variables": {"stage": {"default": "live"}}}]

    def test_renders_a_tuple_as_a_list(self) -> None:
        operation = openapi.Operation(tags=("users", "admin"))

        assert openapi.to_dict(operation) == {"tags": ["users", "admin"]}

    @pytest.mark.parametrize("value", ["text", b"bytes", 3, True, None])
    def test_leaves_a_scalar_alone(self, value: object) -> None:
        # a string is a Sequence, so walking it would explode it into characters
        assert openapi.to_dict(value) == value

    def test_leaves_a_dataclass_type_alone(self) -> None:
        # only instances carry values; the class itself has nothing to render
        assert openapi.to_dict(openapi.Contact) is openapi.Contact

    def test_spreads_extensions_into_the_object(self) -> None:
        tag = openapi.Tag(name="users", extensions={"x-internal": True})

        assert openapi.to_dict(tag) == {"name": "users", "x-internal": True}

    def test_rejects_an_extension_key_that_is_not_prefixed(self) -> None:
        tag = openapi.Tag(name="users", extensions={"internal": True})

        with pytest.raises(ValueError, match="must start with 'x-'"):
            openapi.to_dict(tag)


class TestOpenAPI:
    def test_renders_a_document(self) -> None:
        document = openapi.OpenAPI(
            info=openapi.Info(title="Demo", version="1.0", license=openapi.License(name="MIT", identifier="MIT")),
            paths={"/users": openapi.PathItem(get=openapi.Operation(operation_id="listUsers"))},
            components=openapi.Components(schemas={"User": {"type": "object"}}),
        )

        assert openapi.to_dict(document) == {
            "openapi": "3.1.1",
            "info": {"title": "Demo", "version": "1.0", "license": {"name": "MIT", "identifier": "MIT"}},
            "paths": {"/users": {"get": {"operationId": "listUsers"}}},
            "components": {"schemas": {"User": {"type": "object"}}},
        }

    def test_accepts_a_document_that_declares_only_webhooks(self) -> None:
        document = openapi.OpenAPI(
            info=openapi.Info(title="Demo", version="1.0"),
            webhooks={"userCreated": openapi.PathItem(post=openapi.Operation())},
        )

        assert openapi.to_dict(document)["webhooks"] == {"userCreated": {"post": {}}}

    @pytest.mark.parametrize("version", ["3.0.3", "3.10.0", "4.0.0"])
    def test_rejects_a_version_it_does_not_describe(self, version: str) -> None:
        with pytest.raises(ValueError, match="Unsupported OpenAPI version"):
            openapi.OpenAPI(info=openapi.Info(title="Demo", version="1.0"), openapi=version)

    def test_accepts_any_patch_release_of_3_1(self) -> None:
        document = openapi.OpenAPI(info=openapi.Info(title="Demo", version="1.0"), openapi="3.1.0")

        assert document.openapi == "3.1.0"

    def test_rejects_a_path_without_a_leading_slash(self) -> None:
        with pytest.raises(ValueError, match="must start with '/'"):
            openapi.OpenAPI(info=openapi.Info(title="Demo", version="1.0"), paths={"users": openapi.PathItem()})


class TestParameter:
    def test_requires_a_path_parameter_to_be_required(self) -> None:
        with pytest.raises(ValueError, match="Path parameter 'id' must be required"):
            openapi.Parameter(name="id", in_=openapi.ParameterLocation.PATH)

    def test_accepts_a_required_path_parameter(self) -> None:
        parameter = openapi.Parameter(name="id", in_=openapi.ParameterLocation.PATH, required=True)

        assert parameter.required is True

    def test_accepts_an_optional_parameter_elsewhere(self) -> None:
        parameter = openapi.Parameter(name="page", in_=openapi.ParameterLocation.QUERY)

        assert parameter.required is None


class TestSecurityScheme:
    @pytest.mark.parametrize(
        ("type_", "missing"),
        [
            (openapi.SecuritySchemeType.API_KEY, "'name', 'in_'"),
            (openapi.SecuritySchemeType.HTTP, "'scheme'"),
            (openapi.SecuritySchemeType.OAUTH2, "'flows'"),
            (openapi.SecuritySchemeType.OPEN_ID_CONNECT, "'open_id_connect_url'"),
        ],
    )
    def test_reports_every_member_a_type_needs(self, type_: openapi.SecuritySchemeType, missing: str) -> None:
        with pytest.raises(ValueError, match=missing):
            openapi.SecurityScheme(type=type_)

    def test_accepts_a_type_that_needs_nothing_else(self) -> None:
        scheme = openapi.SecurityScheme(type=openapi.SecuritySchemeType.MUTUAL_TLS)

        assert openapi.to_dict(scheme) == {"type": "mutualTLS"}

    def test_accepts_a_complete_scheme(self) -> None:
        scheme = openapi.SecurityScheme(
            type=openapi.SecuritySchemeType.API_KEY,
            name="X-Api-Key",
            in_=openapi.ParameterLocation.HEADER,
        )

        assert openapi.to_dict(scheme) == {"type": "apiKey", "name": "X-Api-Key", "in": "header"}


class TestOAuthFlows:
    @pytest.mark.parametrize(
        ("build", "missing"),
        [
            (lambda flow: openapi.OAuthFlows(implicit=flow), "implicit flow is missing 'authorization_url'"),
            (lambda flow: openapi.OAuthFlows(password=flow), "password flow is missing 'token_url'"),
            (
                lambda flow: openapi.OAuthFlows(client_credentials=flow),
                "client_credentials flow is missing 'token_url'",
            ),
            (
                lambda flow: openapi.OAuthFlows(authorization_code=flow),
                "authorization_code flow is missing 'authorization_url', 'token_url'",
            ),
        ],
    )
    def test_reports_the_urls_a_flow_cannot_work_without(
        self,
        build: typing.Callable[[openapi.OAuthFlow], openapi.OAuthFlows],
        missing: str,
    ) -> None:
        with pytest.raises(ValueError, match=missing):
            build(openapi.OAuthFlow(scopes={}))

    def test_accepts_a_complete_flow(self) -> None:
        flows = openapi.OAuthFlows(
            authorization_code=openapi.OAuthFlow(
                scopes={"read": "Read everything"},
                authorization_url="/authorize",
                token_url="/token",
            )
        )

        assert openapi.to_dict(flows) == {
            "authorizationCode": {
                "scopes": {"read": "Read everything"},
                "authorizationUrl": "/authorize",
                "tokenUrl": "/token",
            }
        }

    def test_accepts_an_object_declaring_no_flows(self) -> None:
        assert openapi.to_dict(openapi.OAuthFlows()) == {}


class TestPathItem:
    @pytest.mark.parametrize("method", ["get", "PATCH"])
    def test_places_an_operation_under_its_method(self, method: str) -> None:
        item = openapi.PathItem()

        placed = item.with_operation(method, openapi.Operation(operation_id="op"))

        assert openapi.to_dict(placed) == {method.lower(): {"operationId": "op"}}

    def test_leaves_the_original_untouched(self) -> None:
        item = openapi.PathItem(get=openapi.Operation(operation_id="read"))

        placed = item.with_operation("POST", openapi.Operation(operation_id="write"))

        assert openapi.to_dict(item) == {"get": {"operationId": "read"}}
        assert openapi.to_dict(placed) == {"get": {"operationId": "read"}, "post": {"operationId": "write"}}

    def test_rejects_a_method_no_path_item_describes(self) -> None:
        item = openapi.PathItem()

        with pytest.raises(ValueError, match="no 'CONNECT' operation"):
            item.with_operation("CONNECT", openapi.Operation())
