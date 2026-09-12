# Kupala Framework

A set of extensions for Starlette for rapid application development.

![PyPI](https://img.shields.io/pypi/v/kupala)
![GitHub Workflow Status](https://img.shields.io/github/workflow/status/alex-oleshkevich/kupala/Lint)
![GitHub](https://img.shields.io/github/license/alex-oleshkevich/kupala)
![Libraries.io dependency status for latest release](https://img.shields.io/librariesio/release/pypi/kupala)
![PyPI - Downloads](https://img.shields.io/pypi/dm/kupala)
![GitHub Release Date](https://img.shields.io/github/release-date/alex-oleshkevich/kupala)
![Lines of code](https://img.shields.io/tokei/lines/github/alex-oleshkevich/kupala)

## Installation

Install `kupala` using PIP or poetry:

```bash
pip install kupala
# or
poetry add kupala
```

## Features

- dependency injection
- SQLAlchemy 2 intergration
- wtforms integration
- click integration
- jinja integration
- file storage abstraction (S3, local files, in memory)
- mail delivery
- authentication (multi-backend, remember me)
- django-like choices enums
- configuration secrets reader
- chainable guards (function that control access to the endpoint)
- pagination
- decorator-style routing
- composable routing

## Quick start

See example application in `examples/` directory of this repository.

## Application dependencies

Application bindings map types to asynchronous resolvers. A resolver receives the current invocation context,
so it can read lifespan state or resolve another dependency without constructing shared request-scoped values.

```python
from kupala import Kupala, Routes
from kupala.dependencies import InvocationContext


class Mailer: ...


async def resolve_mailer(context: InvocationContext) -> object:
    return Mailer()


app = Kupala("example", routes=Routes(), bindings={Mailer: resolve_mailer})
```

Extensions contribute the same resolver mapping through `AppBuilder.bindings`. Use `constant(value)` when an
already-constructed value should be returned unchanged.

## Basic credentials

`BasicAuth` is a regular dependency binding. It returns `BasicCredentials` directly, or accepts an `authenticate=`
callback and returns its `Identity[T]`. HTTP Basic sends a reusable password with every request, so use it only over
HTTPS.

```python
from typing import Annotated

from kupala import BasicAuth, BasicCredentials, Identity
from kupala.errors import InvalidCredentialsError

type Credentials = Annotated[BasicCredentials, BasicAuth(realm="api")]


async def authenticate(credentials: BasicCredentials, users: UserRepository) -> Identity[User]:
    user = await users.for_password(credentials.username, credentials.password)
    if user is None:
        raise InvalidCredentialsError()
    return Identity(user)


type CurrentIdentity = Annotated[
    Identity[User],
    BasicAuth(realm="api", authenticate=authenticate),
]
```

## API keys

`APIKey` reads one named header, query parameter, or cookie. It returns the raw key unless `authenticate=` is
provided, in which case it returns the callback's `Identity[T]`. Missing, empty, or rejected keys return 403 by
default; pass `error=` only when the application deliberately provides another HTTP error policy.

```python
from typing import Annotated

from kupala import APIKey, Identity
from kupala.errors import InvalidCredentialsError


async def authenticate(key: str, keys: KeyRepository) -> Identity[ServiceAccount]:
    account = await keys.find(key)
    if account is None:
        raise InvalidCredentialsError()
    return Identity(account)


type CurrentIdentity = Annotated[
    Identity[ServiceAccount],
    APIKey(
        name="accessKey",
        key_name="X-API-Key",
        location="header",
        authenticate=authenticate,
    ),
]
```

Prefer headers. Query keys commonly leak through URLs and logs; cookie keys need the application's normal CSRF
protection because browsers attach them automatically.

## Bearer credentials

`Bearer` is a regular dependency binding that returns the raw credential and adds the matching security scheme to
OpenAPI. Pass `authenticate=` to resolve an `Identity[T]` instead; the callback's first parameter receives the token,
and its remaining parameters use normal dependency injection. Raising `InvalidCredentialsError` directly from the
callback produces the configured Bearer challenge without exposing the token.

```python
from typing import Annotated

from kupala import Bearer, Response

type AccessToken = Annotated[str, Bearer(name="accessToken", bearer_format="JWT", realm="api")]


async def endpoint(token: AccessToken) -> Response: ...
```

```python
from kupala import Bearer, Identity
from kupala.errors import InvalidCredentialsError


async def authenticate(token: str, users: UserRepository) -> Identity[User]:
    user = await users.for_token(token)
    if user is None:
        raise InvalidCredentialsError()
    return Identity(user)


type CurrentIdentity = Annotated[
    Identity[User],
    Bearer(realm="api", name="accessToken", bearer_format="JWT", authenticate=authenticate),
]
```
