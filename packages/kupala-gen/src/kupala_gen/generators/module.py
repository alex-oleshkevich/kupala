import keyword
import pathlib
import re

import click
import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from kupala_gen.plans import ChangePlan, CreateDirectory, CreateFile, ModifyFile
from kupala_gen.projects import discover_project
from kupala_gen.runtime import GenerationContext
from kupala_gen.runtime import generator as generator_command


class _AddRoutesChild(cst.CSTTransformer):
    def __init__(self, child: str) -> None:
        self.child = child
        self.matches = 0

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        if (
            len(original_node.targets) != 1
            or not isinstance(original_node.targets[0].target, cst.Name)
            or original_node.targets[0].target.value != "routes"
            or not isinstance(updated_node.value, cst.Call)
            or not isinstance(updated_node.value.func, cst.Name)
            or updated_node.value.func.value != "Routes"
        ):
            return updated_node

        self.matches += 1
        call = updated_node.value
        children = tuple(
            argument for argument in call.args if argument.keyword is not None and argument.keyword.value == "children"
        )
        if len(children) > 1:
            raise click.UsageError("Routes() has more than one children argument.")

        if not children:
            value = cst.Tuple((cst.Element(cst.Name(self.child)),))
            equal = cst.AssignEqual(cst.SimpleWhitespace(""), cst.SimpleWhitespace(""))
            argument = cst.Arg(value, keyword=cst.Name("children"), equal=equal)
            return updated_node.with_changes(value=call.with_changes(args=(*call.args, argument)))

        argument = children[0]
        value = argument.value
        if not isinstance(value, (cst.List, cst.Tuple)):
            raise click.UsageError("Routes children must be a literal list or tuple.")

        if any(isinstance(element, cst.StarredElement) for element in value.elements):
            raise click.UsageError("Routes children must be a literal list or tuple.")

        if any(isinstance(element.value, cst.Name) and element.value.value == self.child for element in value.elements):
            return updated_node

        elements = [*value.elements, cst.Element(cst.Name(self.child))]
        previous = elements[-2]
        if (
            isinstance(previous, cst.Element)
            and isinstance(previous.comma, cst.Comma)
            and isinstance(previous.comma.whitespace_after, cst.SimpleWhitespace)
            and not previous.comma.whitespace_after.value
        ):
            comma = previous.comma.with_changes(whitespace_after=cst.SimpleWhitespace(" "))
            elements[-2] = previous.with_changes(comma=comma)

        arguments = list(call.args)
        index = arguments.index(argument)
        arguments[index] = argument.with_changes(value=value.with_changes(elements=tuple(elements)))
        return updated_node.with_changes(value=call.with_changes(args=tuple(arguments)))


def _add_routes_child(source: bytes, package_name: str, module_name: str, path: pathlib.Path) -> bytes:
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError as error:
        raise click.UsageError(f"Could not parse {path}: {error.message}") from None

    child = f"{module_name}_routes"
    transform = _AddRoutesChild(child)
    tree = tree.visit(transform)
    if transform.matches != 1:
        raise click.UsageError(f"Expected one routes = Routes(...) assignment in {path}.")

    context = CodemodContext()
    AddImportsVisitor.add_needed_import(
        context,
        f"{package_name}.{module_name}.routes",
        "routes",
        asname=child,
    )
    return AddImportsVisitor(context).transform_module(tree).bytes


@generator_command()
@click.command("module")
@click.argument("name")
def generator(context: GenerationContext, name: str) -> ChangePlan:
    """Add an application module."""

    if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name) is None or keyword.iskeyword(name):
        raise click.BadParameter("must be a canonical snake_case Python name", param_hint="name")

    project = discover_project(context.target_root)
    source = project.routes_file.read_bytes()
    routes = _add_routes_child(source, project.package_name, name, project.routes_file)
    module = project.package.relative_to(project.root) / name
    return ChangePlan(
        (
            CreateDirectory(module),
            CreateFile(module / "__init__.py", ""),
            CreateFile(module / "routes.py", "from kupala.routing import Routes\n\nroutes = Routes()\n"),
            ModifyFile(project.routes_file.relative_to(project.root), source, routes),
        )
    )
