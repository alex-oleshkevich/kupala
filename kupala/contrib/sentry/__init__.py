import contextlib
import sentry_sdk
import typing
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.types import AppType

from kupala.extensions import Extension


class SentryExtension(Extension):
    def __init__(
        self,
        dsn: str | None,
        environment: str = "",
        release_id: str = "",
        sentry_options: dict[str, typing.Any] | None = None,
        integrations: typing.Sequence[sentry_sdk.integrations.Integration] | None = None,
    ) -> None:
        self.dsn = dsn
        self.environment = environment
        self.release_id = release_id
        self.sentry_options = sentry_options or {}
        self.integrations = integrations or []

    @contextlib.asynccontextmanager
    async def bootstrap(self, app: AppType) -> typing.AsyncIterator[typing.Mapping[str, typing.Any]]:
        if self.dsn:
            sentry_sdk.init(
                self.dsn,
                environment=self.environment,
                release=self.release_id,
                **self.sentry_options,
                integrations=[
                    StarletteIntegration(),
                    *self.integrations,
                ],
            )
        yield {}
