import re
import typing as t

from marshmallow import Schema
from starlette import datastructures as ds, requests

from kupala.sessions import Session
from kupala.support import DictBag

if t.TYPE_CHECKING:
    from kupala.application import App
    from kupala.authentication import AuthState

undefined = object()

Caster = t.Callable[[t.Any], t.Any]


class FormData(requests.FormData):
    pass


class QueryParams(ds.QueryParams):
    def get_int(self, name: str, default: int = None) -> int:
        return self.get(name, default, int)

    def get_float(self, name: str, default: float = None) -> float:
        return self.get(name, default, float)

    def get_int_list(self, name: str) -> list[int]:
        return t.cast(list[int], self.getlist(name, int))

    def get_float_list(self, name: str) -> list[float]:
        return t.cast(list[float], self.getlist(name, float))

    def get_list(self, name: str) -> list:
        return self.getlist(name)

    def get(
        self,
        name: str,
        default: t.Any = None,
        cast: Caster = None,
    ) -> t.Any:
        value = super().get(name, default)
        if cast and value is not None:
            value = cast(value)
        return value

    def getlist(self, name: str, cast: Caster = None) -> list[str]:
        value = super().getlist(name)
        if cast:
            value = list(map(cast, value))
        return value


class Request(requests.Request):
    _query_params: QueryParams

    @property
    def app(self) -> "App":
        return self.scope["app"]

    @property
    def auth(self) -> "AuthState":
        assert (
            "auth" in self.scope
        ), "AuthenticationMiddleware must be installed to access request.auth"
        return self.scope["auth"]

    @property
    def wants_json(self) -> bool:
        """Test if request sends Accept header
        with 'application/json' value."""
        return "application/json" in self.headers.get("accept", "")

    @property
    def is_ajax(self) -> bool:
        """
        Is true when the request is a XMLHttpRequest.
        It works if JavaScript's HTTP client sets an X-Requested-With HTTP header.

        Known frameworks:
        http://en.wikipedia.org/wiki/List_of_Ajax_frameworks#JavaScript
        """
        return self.headers.get("x-requested-with", None) == "XMLHttpRequest"

    @property
    def ip(self) -> str:
        """Returns the IP address of user."""
        return self.client.host

    @property
    def secure(self) -> bool:
        """Determine if the request served over SSL."""
        return self.scope["scheme"] == "https"

    @property
    def is_post(self) -> bool:
        """Test if request was made using POST method."""
        return self.method.upper() == "POST"

    @property
    def query_params(self) -> QueryParams:
        """Return query parameters."""
        if not hasattr(self, "_query_params"):
            self._query_params = QueryParams(self.scope.get("query_string", ""))
        return self._query_params

    @property
    def session(self) -> Session:  # type: ignore[override]
        assert (
            "session" in self.scope
        ), "SessionMiddleware must be installed to access request.session"
        return self.scope["session"]

    def old_data(self, key: str = None) -> t.Union[dict, t.Any]:
        """Retrieve input data from the previous request."""
        data = self.session.pop("_redirect_data", {})
        if key:
            return data.get(key)
        return data

    def errors(self) -> DictBag[list[str]]:
        """Retrieve validation errors from the previous request."""
        return DictBag(self.session.pop("errors", {}))

    def url_matches(self, *patterns: str) -> bool:
        for pattern in patterns:
            if pattern == self.url.path:
                return True
            if re.match(pattern, self.url.path):
                return True
        return False

    def full_url_matches(self, *patterns: str) -> bool:
        for pattern in patterns:
            if pattern == str(self.url):
                return True
            if re.match(pattern, str(self.url)):
                return True
        return False

    async def validate(
        self,
        schema_class: t.Type[Schema],
        only: t.Sequence[str] = None,
        exclude: t.Sequence[str] = None,
        partial: bool = False,
        unknown: str = "exclude",
    ) -> dict:
        """Validate input data. Raises marshmallow.ValidationError when invalid."""
        schema = schema_class(
            only=only, exclude=exclude or [], partial=partial, unknown=unknown
        )
        return schema.load(await self.form())
