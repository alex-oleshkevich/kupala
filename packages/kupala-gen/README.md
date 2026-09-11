# kupala-gen

Code generation for Kupala applications: projects, modules, and features.

```bash
uvx --from 'kupala[gen]' kupala gen --help
```

## Commands

| Command | What it does |
| --- | --- |
| `kupala gen new` | scaffold a project |
| `kupala gen new-module` | add a module to the current project |
| `kupala gen add <generator>` | run a generator |

## Writing a generator

Every generator answers as a subcommand of `add`, and any package can contribute one through the
`kupala.generators` entry point group. The target *is* the command:

```python
# my_package/generators.py
import click


@click.command("widget")
def generator() -> None:
    """Add a widget to the project."""
    click.echo("widget")
```

```toml
[project.entry-points."kupala.generators"]
widget = "my_package.generators:generator"
```

Generators load when `gen` runs, before `add` is asked for a command, so installing the package is
enough to make `kupala gen add widget` work. One that fails to import, or whose target is not a
click command, is logged and skipped rather than breaking the command line.
