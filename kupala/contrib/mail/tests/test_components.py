from kupala.contrib.mail.components import Envelope, MailComponent


class DummyComponent(MailComponent):
    def render(self) -> str:
        return "hello"


def test_envelope() -> None:
    component = Envelope(body=DummyComponent())
    assert "hello" in str(component)
