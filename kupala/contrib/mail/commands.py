import click
import datetime
import typing

from kupala.console import async_command
from kupala.contrib.mail.mails import Mails

mail_commands: click.Group = click.Group("mail")


@mail_commands.command("test")
@click.argument("email")
@click.option("--subject", default="This is test email")
@click.option("--body", default="If you see this then it works. Sent at {time}.")
@click.option("--mailer", default="default")
@click.pass_context
@async_command
async def send_test_email_command(context: click.Context, email: str, subject: str, body: str, mailer: str) -> None:
    send_date = datetime.datetime.now()
    mails = typing.cast(Mails, context.obj["app"].state.mail_ext)
    await mails.send_mail(to=email, subject=subject, text=body.format(time=send_date), mailer=mailer)
    click.echo("Message has been sent.")
