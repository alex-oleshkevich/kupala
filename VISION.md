# Motivation

The Python ecosystem already offers a wide range of web frameworks, each with a different set of goals. Many of the popular choices are microframeworks: they are flexible and lightweight, but they leave the developer responsible for selecting and integrating critical pieces such as security, persistence, and deployment. That freedom is valuable, yet it demands deep prior experience and tends to produce one-off project layouts, which slows automation and knowledge transfer. Django serves as the clearest point of comparison. It provides a comprehensive toolkit, but it also relies on hidden behaviors and bespoke subsystems. Kupala prefers to assemble well-known, composable building blocks rather than introduce another layer of framework-specific conventions.

Kupala therefore aims to deliver a complete stack that covers the day-to-day needs of a modern web application while keeping the developer focused on business logic. In practice that means the framework:

- embraces async-first design and ships with full type hints;
- prefers developer performance over framework performance;
- scales in complexity only as the project grows, rather than front-loading ceremony;
- bundles the essentials - admin, mail, database, job queues, websockets, OAuth, caching, forms, asset pipelines, internationalization, and more - without locking teams into one path;
- treats code generation as a productivity booster, not a straightjacket;
- offers a developer experience on par with Rails, Django, Laravel, or Phoenix; and
- favors clean extension points over forking or monkey-patching.

## The vision

The guiding idea is simple: start small, end big. A Kupala project should begin as a pair of files and scale to a high-traffic, multi-service system without rewrites or architectural dead ends. Developers ought to spend their time delivering business value, not wiring together the same plumbing for every new project or repeating the setup work they've done a dozen times before.

## Tech Stack

- Starlette for http and websocket handling
- Click for command line commands

# Strategies

Kupala focuses on providing a consistent developer experience for the common tasks involved in building a web application. The principles below are grouped to show how they support the overall vision.

## Architecture

- Library first, framework second: every component remains usable as a standard Python import so that projects can adopt Kupala gradually.
- Composable architecture: wherever possible, Kupala relies on Python protocols and well-defined interfaces. Swapping an implementation should not require rewriting the surrounding code.
- No hidden globals: state lives where it is defined. The framework avoids secret registries, singletons, and implicit behavior.
- Zero lock-in: Kupala stands on Starlette, SQLAlchemy, Click, Jinja, WTForms, Alembic, and other well-known libraries. There is no proprietary runtime to escape.
- Transparent architecture: developers interact with their own code. There is no hidden "core" that rewrites behavior behind the scenes.
- One way to do it: the framework highlights a single path that works well instead of presenting a maze of competing patterns.
- Clear integration points: extensions plug in through documented APIs rather than reaching into internals.
- Use existing libraries: Kupala favors established third-party packages instead of reimplementing them.

## Tooling

- Integrated tooling: the command-line interface ships with the framework, is fully supported, and is treated as part of the public surface.
- Code generation with intent: scaffolders exist to save time and make defaults clear, but the generated code belongs to the developer and can be extended or replaced.
- Batteries included: Kupala bundles mail delivery, background jobs, configuration management, and similar building blocks. Teams can adopt them immediately or swap in alternatives as needed.
- Standard directory layout: the framework recommends a conventional project structure so that codemods, extensions, and documentation can assume a predictable shape.

# Developer experience

This is one of primary goals.

- Tooling: automate the repeatable work so developers can spend their time on product logic instead of setup chores.
- Minimal cognitive load: sensible defaults guide the early stages of a project, and configuration remains incremental. There is no heavy ceremony or DDD boilerplate to clear before you can ship.
- Single mental model: the same patterns apply to views, APIs, jobs, channels, admin actions, and forms. Moving between features should feel familiar.
- Testing harness: Include fixtures, factories, and snapshot helpers so writing tests feels first-class from the start.
- Full-stack by default: whether you build API service, server side rendered templates, or realtime app - the frameworks gives you full support.
- Batteries included: the shipped integrations are production-ready and come with recommended configurations for observability, deployment, and runtime health checks.
- Convenience and helpers: common objects - like Request or Form, offer convenience methods for parsing payloads, detecting content types, and validating data, reducing boilerplate through small, thoughtfully designed helpers. Same applies to any other component.

# Non-goals

- Kupala is not a microframework; it ships with opinions and batteries so teams can move quickly.
- It does not hide your code behind magic. Every moving part stays visible and debuggable.
- There is no proprietary runtime. Deploy it like any other Python application.
- The focus isn’t a JSON-only API toolkit; HTML rendering and hybrid stacks remain first-class.
- Configuration stays code-driven. We avoid declarative DSLs that drift from Python.

# Success Criteria

- A first-time user can scaffold and run a working application in under three minutes.
- A senior engineer can grow that application to serve a million users without re-platforming.
- Core capabilities—authentication, admin, APIs, jobs, forms - arrive as optional modules rather than hard-wired dependencies.
- Roughly 80% of common SaaS features are available through a single command or extension, plus a small amount of ergonomic, generated code.
- Teams can introduce Kupala incrementally into existing Starlette projects.
- Extensions ship as separate packages, install with pip, and integrate cleanly with the CLI.

# Inspirations

- Django — the benchmark for batteries-included frameworks; its admin, auth, and tooling model inform Lunette’s defaults while we aim for less hidden magic.
- Pyramid — demonstrates how composable building blocks and well-defined extension points can scale from micro to full-stack applications.
- Phoenix — sets the standard for real-time features, live updates, and a cohesive developer workflow in the BEAM ecosystem.
- Laravel & Ruby on Rails — showcase polished developer ergonomics, expressive generators, and tight feedback loops that Lunette strives to match.
- Symfony — illustrates how modular PHP components can coexist within and outside the framework, guiding Lunette’s “library first” approach.
