# kupala-gen

Code generation for Kupala applications: projects, modules, and features.

```bash
uvx --from 'kupala[gen]' kupala gen --help
```

## Commands

| Command | What it does |
| --- | --- |
| `kupala gen new` | scaffold a project |
| `kupala gen add <generator>` | run a generator |

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

Generators load when `gen` runs, before `add` is asked for a command, so installing the package is
enough to make `kupala gen add widget` work. One that fails to import, or whose target is not a
click command, is logged and skipped rather than breaking the command line.

Every run resolves explicit Click values before interview answers and defaults, prepares and previews
the complete change plan before writing, and applies it with conflict checks and rollback. `--yes`
never prompts, while `--dry-run` never writes.

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

## CLI registration contract

A `kupala.commands` entry point targets a callback that accepts `kupala.commands.Commands`. Kupala
calls the callback with a fresh registry for every CLI build, then compiles its definitions through
Kupala's dependency-injection path. Groups such as `gen` run without resolving `KUPALA_APP`.
Application commands load lazily when no installed command matches. Plugin failures are logged
without exception details.
