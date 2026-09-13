# kupala-gen

Code generation for Kupala applications: projects, modules, and features.

```bash
uvx --from 'kupala[gen]' kupala gen --help
```

## Commands

| Command | What it does |
| --- | --- |
| `kupala new [PATH]` | scaffold a project without loading an application |
| `kupala gen new [PATH]` | scaffold a project |
| `kupala gen add <generator>` | run a generator |
| `kupala gen add module NAME` | add a module and compose its routes |

`kupala new` and `kupala gen new` are equivalent. `PATH` is created and defaults to the current directory;
use `--force` when it already exists.
`--template` defaults to `standard`; the bundled choices are `minimal`, `standard`, and `api`.
All three create a packaged application with tests and deployment files. `minimal` keeps the application
in one module, `standard` adds templates and static files, and `api` adds an OpenAPI extension. Use
`--workspace` to create a uv workspace with the selected template under `PATH/src`. Use `--dry-run`
to preview, `--diff` to show file diffs, `--yes` to apply without confirmation, and `--force` only
for files a template explicitly marks as replaceable. Project creation confirmation defaults to yes.

Custom templates use an HTTPS Git URL or absolute `file://` URI as `--template`. They require an
interactive trust confirmation or `--trust-template`; `--yes` does not grant trust. Git sources accept
`--ref`. Pass values with repeated `--answer KEY=VALUE` options. Generated files belong to the project
and are never overwritten when their contents diverge unless the operation explicitly permits it.

## Writing a generator

Every generator answers as a subcommand of `add`, and any package can contribute one through the
`kupala.generators` entry point group. The target *is* the command:

```python
import click

from kupala_gen import ChangePlan, CreateFile, GenerationContext, Question, generator


@generator(questions=(Question("name", "Widget name"),))
@click.command("widget")
@click.option("--name")
def widget(context: GenerationContext, name: str) -> ChangePlan:
    """Add a widget to the project."""
    return ChangePlan((CreateFile(f"{name}.py", ""),))
```

```toml
[project.entry-points."kupala.generators"]
widget = "my_package.generators:widget"
```

Generator names are discovered without importing their commands. The selected generator loads when
it is invoked, and a broken generator reports an error without blocking the others.

Every run resolves explicit Click values before interview answers and defaults, previews the complete
change plan without file diffs unless `--diff` is set, and applies it with conflict checks and rollback.
`--yes` never prompts, while `--dry-run` never writes.

Bound questions must use scalar, value-exposing Click parameters without prompts or callbacks.
Command-line values are explicit;
environment and `default_map` values are rejected so they cannot silently replace interview answers.
`--force` only affects a `CreateFile` marked `overwriteable=True`; it never bypasses a modification
baseline or a concurrent-edit check. Sensitive operations show their path and status without a diff.

Template-backed commands can call `run_generation()` with questions discovered at runtime instead of
using the decorator. It accepts the same `Question` sequence, explicit answer mapping, target root,
flags, and planner returning `ChangePlan`, so both paths use identical validation and filesystem safety.
Failures expose structured operation statuses, retain unusable backups for recovery, and do not print
secret answers or arbitrary planner exceptions.

Template sources use `BundledTemplate`, `GitTemplate`, or `FileTemplate`. Resolve them inside the
`resolve_template()` context, inspect their supported Copier questions with `inspect_template()`, and
render complete answers with `render_template()`. Resolution snapshots the source before inspection;
Git accepts only HTTPS and uses Dulwich, while `file://` directories require explicit trust. Rendering
uses Copier with prompting and unsafe features disabled and returns a `ChangePlan` without touching the
target project. ZIP sources are not supported.

## CLI registration contract

A `kupala.commands` entry point targets a callback that accepts `kupala.commands.Commands`. Kupala
calls the callback with a fresh registry for every CLI build, then compiles its definitions through
Kupala's dependency-injection path. Groups such as `gen` run without resolving `KUPALA_APP`.
Application-independent leaf commands use `BootstrapCommand` and `Commands.bootstrap()`.
Application commands load lazily when no installed command matches. Plugin failures are logged
without exception details.
