import hashlib
import hmac
import os
import typing
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer
from starlette.types import ASGIApp, Receive, Scope, Send

from kupala.exceptions import NotAuthorized
from kupala.requests import Request, is_submitted

CSRF_SESSION_KEY = "_csrf_token"
CSRF_HEADER = "x-csrf-token"
CSRF_QUERY_PARAM = "csrf-token"
CSRF_POST_FIELD = "_token"


class CSRFError(Exception):
    pass


class TokenMissingError(CSRFError):
    pass


class TokenExpiredError(CSRFError):
    pass


class TokenDecodeError(CSRFError):
    pass


class TokenMismatchError(CSRFError):
    pass


def get_generate_random(length: int = 64) -> str:
    return hashlib.sha1(os.urandom(length)).hexdigest()


def generate_token(secret_key: str, data: str) -> str:
    return hmac.new(secret_key.encode(), data.encode(), "sha256").hexdigest()


def validate_csrf_token(
    session_token: str,
    timed_token: str,
    secret_key: str,
    salt: str = "_csrf_",
    max_age: int | None = None,
) -> bool:
    if not timed_token or not session_token:
        raise TokenMissingError("CSRF token is missing.")

    try:
        serializer = URLSafeTimedSerializer(secret_key, salt=salt)
        raw_token = serializer.loads(timed_token, max_age=max_age)
    except SignatureExpired:
        raise TokenExpiredError("CSRF token has expired.")
    except BadData:
        raise TokenDecodeError("CSRF token is invalid.")

    if not hmac.compare_digest(session_token, raw_token):
        raise TokenMismatchError("CSRF tokens do not match.")
    return True


class CSRFMiddleware:
    exclude_urls: typing.Iterable[str] | None = None
    safe_methods: typing.Iterable[str] = ["get", "head", "options"]

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        salt: str = "_csrf_",
        exclude_urls: typing.Iterable[str] | None = None,
        max_age: int = 3600,
    ):
        self.app = app
        self._exclude_urls = exclude_urls or self.exclude_urls or []
        self._secret_key = str(secret_key)
        self._salt = salt
        self._max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if "session" not in scope:
            raise CSRFError("CsrfMiddleware requires SessionMiddleware.")

        request = Request(scope, receive, send)
        if CSRF_SESSION_KEY not in request.session:
            token = get_generate_random()
            csrf_token = generate_token(self._secret_key, token)
            request.session[CSRF_SESSION_KEY] = csrf_token

        serializer = URLSafeTimedSerializer(self._secret_key, self._salt)
        timed_token = str(serializer.dumps(request.session[CSRF_SESSION_KEY], self._salt))
        request.state.csrf_token = request.session[CSRF_SESSION_KEY]
        request.state.csrf_timed_token = timed_token

        if self.should_check_token(request):
            try:
                validate_csrf_token(
                    session_token=request.session[CSRF_SESSION_KEY],
                    timed_token=await self.get_csrf_token(request),
                    secret_key=self._secret_key,
                    salt=self._salt,
                    max_age=self._max_age,
                )
            except CSRFError as ex:
                raise NotAuthorized(detail="CSRF token is invalid.") from ex
        await self.app(scope, receive, send)

    async def get_csrf_token(self, request: Request) -> str:
        from_headers = request.headers.get(CSRF_HEADER, "")
        from_query = request.query_params.get(CSRF_QUERY_PARAM, "")
        from_form_data = ""
        if is_submitted(request):
            form_data = await request.form()
            from_form_data = typing.cast(str, form_data.get(CSRF_POST_FIELD))
        return from_query or from_form_data or from_headers

    def should_check_token(self, request: Request) -> bool:
        return not any(
            [
                request.method.lower() in self.safe_methods,
                *[exclusion in str(request.url) for exclusion in self._exclude_urls],
            ]
        )


def get_csrf_token(request: Request) -> str | None:
    return request.state.csrf_timed_token if hasattr(request.state, "csrf_timed_token") else None


def get_csrf_input(request: Request) -> str:
    token = get_csrf_token(request) or ""
    return f'<input type="hidden" name="{CSRF_POST_FIELD}" value="{token}">'


def get_csrf_meta_tag(request: Request) -> str:
    token = get_csrf_token(request) or ""
    return f'<meta name="{CSRF_QUERY_PARAM}" content="{token}">'
