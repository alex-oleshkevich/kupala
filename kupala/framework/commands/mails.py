import asyncio

import click

from kupala.mailers import compose


@click.group("mails")
def group() -> None:
    ...


@group.command("send-test-email")
@click.argument("recipient")
@click.option("--mailer", default="default")
def send_test_email(recipient: str, mailer: str) -> None:
    with compose() as composer:
        composer.to(recipient)
        composer.subject("This is a test message")
        composer.text_body("If you see it then email delivery worked.")
        composer.use_html_template("mails/verify_email.html")
        asyncio.run(composer.send(mailer=mailer))
