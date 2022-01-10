from kupala.application import Kupala


def test_passwords() -> None:
    app = Kupala()
    app.passwords.use('pbkdf2_sha256')
    hashed = app.passwords.hash('password')
    assert app.passwords.verify('password', hashed)
