from imia import InMemoryProvider, LoginManager, SessionAuthenticator

from kupala.application import Kupala


def test_authentication() -> None:
    class User:
        pass

    user_provider = InMemoryProvider({})
    app = Kupala()
    app.auth.configure(
        user_model=User, user_provider=InMemoryProvider({}), authenticators=[SessionAuthenticator(user_provider)]
    )
    assert isinstance(app.auth.login_manager, LoginManager)
