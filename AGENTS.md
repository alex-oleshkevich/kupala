Kupala is an asynchronous full-stack web framework for modern Python (3.14+). It lets developers start with a small application and grow it into a high-traffic system without re-platforming or surrendering the composability of the underlying Python ecosystem.

The framework is for Python teams that want a cohesive, batteries-included developer experience while keeping application code explicit, typed, and portable.

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
- Keep transport and command boundaries thin. They translate framework inputs and outputs, then delegate application behavior to the module or optional package that owns it.
- Define external-integration protocols in their owning optional package and implement only adapters required by a current use case. Do not add speculative adapters.
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
- Treat headers, proxy metadata, host values, cookies, forms, uploads, and template-facing values as untrusted input. Validate and bound them at the owning boundary, preserve framework escaping, and test rejection and normalization behavior.
- Never add a dependency or integration that expands the attack surface without documenting its trust and configuration model.
- Before adding a dependency, check the standard library and existing workspace dependencies. If neither fits, verify the current release, explain what code it replaces and its trust model, and get the user's approval before adding it.

## Engineering Discipline

- Implement exactly what was asked — no speculative extra features, files, or abstractions beyond the request.
- State material assumptions before implementation. If plausible interpretations would change the public contract or scope, present the tradeoff and ask instead of choosing silently.
- Do not add comments that merely restate the code. Use comments only when they explain a non-obvious constraint or decision.
- Don't abstract, generalize, or add configurability beyond what's needed right now. The integration protocols required by the project invariants are the deliberate exception, not a license to abstract elsewhere. Before finishing, ask whether a senior engineer would call the change over-engineered; if so, simplify it.
- Touch only what the request requires, match the surrounding style, and avoid adjacent refactoring. Remove code made unused by your change, but report pre-existing dead code instead of deleting it.
- Every changed line must trace directly to the requested outcome.
- Prefer current, idiomatic patterns for the chosen stack over legacy ones (e.g. current Python idioms, no deprecated APIs) — not "modern" for its own sake.

## Beads issue tracker

- Use Beads (`bd`) for durable task tracking and project memory. Do not create parallel markdown TODO lists or ad hoc memory files.
- Run `bd prime` when starting tracked work or when Beads context may be stale.
- Use `bd ready` to find available work, `bd show <id>` to inspect it, `bd update <id> --claim` to claim it, `bd close <id>` when it is complete, and `bd remember` for persistent project knowledge.
- Keep repository-wide working invariants in `AGENTS.md`, package behavior in the owning package's README, and dated measurements, incidents, and task-specific findings in Beads. Remove or replace stale instructions instead of layering exceptions onto them.
- At handoff, report changed files, validation, issue status, and remaining work. Do not commit, push, or synchronize Beads remotes unless explicitly requested.

## Change workflow

- Inspect the current implementation, tests, `git status`, and related Beads issues before editing.
- For non-trivial work, create or claim a Beads issue and record design decisions there.
- For non-trivial work, state a brief plan with verifiable success criteria before editing.
- Make the smallest contract-preserving change. Reproduce bugs with a failing regression test, and run relevant tests before and after refactors.
- Run focused tests, then the full suite, type checks, linting, coverage, and package-build checks.
- Before handoff, run `just verify`. If a required check is missing or wrong, fix the recipe instead of bypassing it with raw commands; fix relevant findings and rerun it until clean.
- Update README or API documentation when public behavior changes.
- Leave unrelated user changes untouched and do not commit, push, publish, or deploy unless explicitly requested.

## Commands

- Keep this list synchronized with the recipes in `justfile`.
- `just dev` — run the demo application with reload on port 7000.
- `just cli $optional_arguments` — run the Kupala CLI from the demo project.
- `just test $optional_test_pattern` — run tests.
- `just test-pkg $package $optional_test_pattern` — run one package's tests.
- `just testc $optional_test_pattern` — run tests with 100% coverage enforcement.
- `just check` — run the full `prek` check suite.
- `just verify` — run the full local CI-equivalent suite: checks, typing, 100% coverage, package builds, and diff validation.

<!-- CODEGRAPH_START -->

## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->
