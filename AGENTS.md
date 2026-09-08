This is Kupala, an asynchrounous full-stack web framework for modern Python (3.14+).

Read @VISION.md for project vision.

# Tone

Be very brief in short. If something can be expressed in single word "Yes", then say "Yes." and nothing more.

# Tech stack

- Starlette plus AnyIO for HTTP, WebSockets, lifespan, and concurrency.
- Jinja for server-rendered templates.
- Click for the CLI.
- pytest with one async testing approach, preferably explicit AnyIO or pytest-asyncio configuration.

- SQLAlchemy 2 and Alembic as an optional database integration.
- RFC-style problem-detail responses for errors, with HTML rendering layered on top.

# Rules

- always use modern Python features, use proper typing from 3.14 and above.
- double think on security
- do not cut edges, ask user if in doubt
- spawn agent with more capable model and higher effor for complex task for architecture decisions
- use language servers for code navigation and search
- use Zuban or another Python language server for symbol navigation, references, and type-aware code changes; use `rg` only for textual searches or when language-server navigation is unavailable
- always make sure that mypy type check pass when you complete your task
- always run `ruff check kupala tests` after code changes and resolve all findings
- use `justfile` recipes instead of shell or temporary scripts.

Important: this git history contains previous version. The current version is complete rethinking and rewrite. Do not peek the old code!

## Testing

- do not create one-time use fixtures, inline then into test function
- Pytest discovers shared fixtures from `tests/conftest.py`; reference them by fixture name in test parameters and do not import or duplicate them in test modules.
- A fixture name ending in `_f` returns a callable factory, so use it as `scope_f(...)`; keep the factory's reusable type contract and test-only aliases in `tests/types.py`.
- Factory fixtures should provide fresh values for common scope attributes on every call and accept keyword overrides for test-specific values.
- In tests, bind request and response-builder objects to local variables before calling methods, such as `request = Request(scope_f())` followed by `response(request).back()`, so LSP has stable symbols and positions for navigation.
- use classes to group related tests `TestRoutes`, instead of separate functions.
- use functions for standalone features that cannot be grouped
- `tests` directory is included into coverage, we don't want dead tests. Use `# pragma: no cover` to exclude dead paths
- when you complete your work, make sure changes are 100% branch covered.

# Components

## Application

File `kupala/applications.py`. Kupala runs custom `Kupala` class harness.

## Routing

File `kupala/routing.py`. Kupala does not use Starlette pattern to register routes, instead it provides `Routes` class with decorators.

## Requests

File `kupala/requests.py`.

## Responses

File `kupala/responses.py`.
It also exports fluide ResponseBuider as `response` helper

## Templates

File `kupala/templates.py`. Template engine protocols and core jinja2 implementation.

## Errors and error handles

File `kupala/errors.py` contains framework exported error definitions, they are automatically handled by built-in error handles.
File `kupala/error_handlers.py` contain default error handlers, they are activated automatically by `Kupala` class.

## Middleware

File `kupala/middleware.py`. Kupala does not use ASGI middleware, instead, it exports simpler middleware protocol (`Middleware`).
But Kupala also accepts ASGI middleware wherever possible for ecosystem compatibility.

## Testing

Files `tests`. Test file names must mirror `kupala/` file structure. For example `kupala/routing.py` -> `tests/test_routing.py`

## Project invariants

- Treat `VISION.md`, `pyproject.toml`, and the public exports in `kupala/__init__.py` as the
  project contract. Note, do not import from exports in tests, use full import name: `from kupala.routing import Routes` instead of `from kupala import Routes`.
- Preserve Starlette and ASGI compatibility at the integration boundary; do not fork or duplicate Starlette behavior without a documented reason.
- Reexport Starlettes classes and utilities from Kupala, user's won't need to update their code if we decide to extend base functionality.
- Keep the core library small. Feature integrations such as database, mail, authentication, storage, and queues must be optional packages or extras unless they are required by the base runtime.
- Do not introduce hidden module-level registries, mutable global state, or implicit application discovery.
- Public APIs require complete type annotations, tests, and documentation of observable behavior.
- Use `logging`, never `print`, in framework code.
- Never expose exception details, secrets, tracebacks, or request data in production responses or logs.

## Async and runtime rules

- Do not perform blocking I/O or CPU-heavy work on the event loop. Dispatch task to threadloop using `starlette.concurrency.run_in_threadpool(fn, *args, **kwargs)`
- Synchronous endpoints must run through the documented threadpool boundary.
- Preserve cancellation, timeout, and lifespan semantics when adding middleware or resource management.
- Middleware must preserve request/response ordering and remain compatible with ASGI middleware where advertised.
- Route compilation must be deterministic and repeatable; route names, prefixes, mounts, hosts, and middleware order are public behavior.

## Error and security rules

- HTTP errors use one documented response contract with content negotiation for HTML and JSON.
- Unhandled exceptions return a generic production response and are logged through the configured logger.
- Session, cookie, upload, form, template, proxy, and host-handling changes require security focused tests.
- Never add a dependency or integration that expands the attack surface without documenting its trust and configuration model.

## Change workflow

- Inspect the current implementation, tests, `git status`, and related Beads issues before editing.
- For non-trivial work, create or claim a Beads issue and record design decisions there.
- Make the smallest contract-preserving change and add a regression test first when fixing behavior.
- Run focused tests, then the full suite, type checks, linting, coverage, and package-build checks.
- Update README or API documentation when public behavior changes.
- Leave unrelated user changes untouched and do not commit, push, publish, or deploy unless explicitly requested.

## Verification commands

- `just check` - runs full check suite with `prek`
- `just test $optional_test_pattern`
- `just testc $optional_test_pattern` - runs tests with coverage
- `uv run mypy`
- `uv build --all-packages --no-sources`
- `git diff --check`

<!-- gortex:communities:start -->
## Community Skills

| Area | Description | Explore |
|------|-------------|---------|
| 2 Dirs Routes | 106 symbols | `analyze(operation:"communities", id:"community-80")` |
| Tests 2 Dirs Kupala Responses Response | 95 symbols | `analyze(operation:"communities", id:"community-71")` |
| 1 Dirs Apply Cookies | 76 symbols | `analyze(operation:"communities", id:"community-8")` |
| Tests 3 Dirs | 69 symbols | `analyze(operation:"communities", id:"community-9")` |
| 2 Dirs Jinjatemplates | 53 symbols | `analyze(operation:"communities", id:"community-81")` |
| 2 Dirs Kupala Responses Serversentevent | 40 symbols | `analyze(operation:"communities", id:"community-72")` |
| 1 Dirs Visit | 38 symbols | `analyze(operation:"communities", id:"community-10")` |
| 2 Dirs Init External Call Dep Kupala Dependencies | 32 symbols | `analyze(operation:"communities", id:"community-56")` |
| 1 Dirs Safe Back Url | 29 symbols | `analyze(operation:"communities", id:"community-6")` |
| Kupala 1 Dirs Basehttperror | 28 symbols | `analyze(operation:"communities", id:"community-64")` |
| 2 Dirs Test Sends Keepalives On A Fixe | 27 symbols | `analyze(operation:"communities", id:"community-73")` |
| Tests Test Client | 21 symbols | `analyze(operation:"communities", id:"community-76")` |
| Kupala 1 Dirs Host | 15 symbols | `analyze(operation:"communities", id:"community-77")` |
| Kupala 1 Dirs Chain Middleware | 14 symbols | `analyze(operation:"communities", id:"community-51")` |
| Kupala Invoke | 12 symbols | `analyze(operation:"communities", id:"community-11")` |
| 2 Dirs Kupala Dependencies Inspect Cal | 12 symbols | `analyze(operation:"communities", id:"community-57")` |
| Tests 2 Dirs Kupala Responses Response | 12 symbols | `analyze(operation:"communities", id:"community-4")` |
| Kupala 1 Dirs Scope | 12 symbols | `analyze(operation:"communities", id:"community-82")` |
| 2 Dirs Init Templates | 10 symbols | `analyze(operation:"communities", id:"community-12")` |
| 1 Dirs Invoke Endpoint | 9 symbols | `analyze(operation:"communities", id:"community-52")` |

<!-- gortex:communities:end -->
