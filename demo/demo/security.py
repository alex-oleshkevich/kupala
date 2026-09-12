import dataclasses
import hmac
import typing

from starlette.requests import HTTPConnection

from demo.settings import Settings
from kupala.dependencies import CompileContext, InvocationContext, ParamInfo, Resolver
from kupala.errors import InvalidCredentialsError
from kupala.schema import openapi
from kupala.security import BasicAuth, BasicCredentials, Identity


@dataclasses.dataclass(frozen=True, slots=True)
class HeaderAPIKey:
    header: str
    scheme_name: str = "demoKey"

    def compile(self, _context: CompileContext, _param: ParamInfo) -> Resolver:
        async def resolve(context: InvocationContext) -> object:
            connection = await context.resolve(HTTPConnection)
            settings = await context.resolve(Settings)
            expected = settings.demo_api_key.get_secret_value()
            supplied = connection.headers.get(self.header)
            if supplied is None or not hmac.compare_digest(supplied.encode(), expected.encode()):
                raise InvalidCredentialsError("Missing or invalid demo API key.")
            return supplied

        return resolve

    def to_openapi(self, _param: ParamInfo, _context: openapi.SchemaContext) -> openapi.Contribution:
        return openapi.Contribution(
            security_schemes={
                self.scheme_name: openapi.SecurityScheme(
                    type=openapi.SecuritySchemeType.API_KEY,
                    name=self.header,
                    in_=openapi.ParameterLocation.HEADER,
                )
            },
            security={self.scheme_name: ()},
            responses={"401": openapi.Response(description="The demo API key is missing or invalid.")},
        )


type DemoAPIKey = typing.Annotated[
    str,
    HeaderAPIKey(header="X-Demo-Key"),
]


def authenticate_basic(credentials: BasicCredentials, settings: Settings) -> Identity[str]:
    username_matches = hmac.compare_digest(credentials.username.encode(), b"demo")
    password_matches = hmac.compare_digest(
        credentials.password.encode(),
        settings.demo_api_key.get_secret_value().encode(),
    )
    if not username_matches or not password_matches:
        raise InvalidCredentialsError("Invalid username or password.")
    return Identity(credentials.username)


type DemoBasicIdentity = typing.Annotated[
    Identity[str],
    BasicAuth[str](realm="Kupala demo", name="demoBasic", authenticate=authenticate_basic),
]
