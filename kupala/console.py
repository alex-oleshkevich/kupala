import click


class CommandGroup(click.Group):
    def add_commands(self, *commands: click.Command) -> None:
        for command in commands:
            self.add_command(command)
