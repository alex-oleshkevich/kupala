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

## Bearer credentials

`Bearer` is a regular dependency binding that returns the raw credential and adds the matching security scheme to
OpenAPI. Missing credentials raise `NotAuthenticatedError`; malformed or duplicate `Authorization` headers raise
`BadRequestError`, and both errors carry the appropriate `WWW-Authenticate` header.

```python
from typing import Annotated

from kupala import Bearer, Response

type AccessToken = Annotated[str, Bearer(name="accessToken", bearer_format="JWT", realm="api")]


async def endpoint(token: AccessToken) -> Response: ...
```
