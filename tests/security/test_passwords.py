from kupala.application import Kupala
from kupala.security.passwords import check_password, make_password


def test_password_utils() -> None:
    app = Kupala()
    password = 'password'
    hashed = make_password(password)
    assert check_password(password, hashed)
    assert app.passwords.verify(password, hashed)
