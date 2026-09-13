# Why Kupala?

Python already has plenty of web frameworks. With a microframework, a team chooses and joins the missing pieces. Larger frameworks provide those pieces together through framework-specific APIs and implicit behaviour. Kupala combines a cohesive full-stack experience with explicit, composable Python libraries.

## Start small, end big

A new application should be small enough to understand at a glance. It should gain structure as the product grows, not because the framework demanded that structure on the first day.

The aim is to begin with a small application and grow into a high-traffic system without changing frameworks or adopting a proprietary runtime. The same application model covers HTTP routes, templates, WebSockets, command-line tools, dependency injection, and extensions.

## Cohesion without hidden machinery

Microframeworks leave most decisions to the application. That freedom works well for experienced teams. Each team must still select, integrate, document, and maintain the missing pieces, which can produce a one-off stack with project-specific conventions.

Comprehensive frameworks solve the coordination problem, but may replace familiar Python tools with their own subsystems. Kupala provides a supported path through common application work while keeping the components visible. Routes live in application code, dependencies are ordinary typed values, and integrations use documented extension points.

## Built on the ecosystem

Kupala uses Starlette for the runtime boundary, Jinja for server-rendered templates, and Click for command-line applications. These libraries remain recognisable and usable as themselves. Application code does not depend on a proprietary server or a configuration language that has to be translated back into Python.

The core stays small. Larger integrations such as databases, mail, storage, and queues belong in optional packages unless the base runtime requires them. Applications can adopt those packages when needed and replace them through explicit interfaces.

## Optimise developer time

Framework performance matters, but developer time is usually scarcer. Kupala favours predictable conventions, complete type information, integrated tooling, and generated code that belongs to the application. It should remove repeated setup work without making the resulting system harder to inspect or debug.

This principle shapes the public API as well: one supported path for common work, with clear integration boundaries when an application needs something different.

## What Kupala is not

Kupala has clear boundaries:

- It is not a microframework; it deliberately provides opinions and a cohesive application model.
- It is not a JSON-only API toolkit; HTML rendering and hybrid applications are first-class use cases.
- It does not hide application behaviour in global registries or require a proprietary deployment platform.

The trade-off is deliberate. Teams that want an unopinionated collection of primitives may prefer Starlette directly. Kupala is for teams that want those foundations assembled into a consistent framework while retaining ordinary Python code and standard ecosystem tools.
