import pytest

from kupala.passwords import Passwords


@pytest.fixture
def passwords() -> Passwords:
    return Passwords()


class TestPasswords:
    def test_password_verification(self, passwords: Passwords) -> None:
        plain_password = "password"
        hashed_password = passwords.make(plain_password)
        assert passwords.verify(plain_password, hashed_password)

    async def test_password_async_verification(self, passwords: Passwords) -> None:
        plain_password = "password"
        hashed_password = await passwords.amake(plain_password)
        assert await passwords.averify(plain_password, hashed_password)

    def test_password_migration(self) -> None:
        plain_password = "password"

        passwords_sha256 = Passwords(["pbkdf2_sha256"])
        passwords_sha512 = Passwords(["pbkdf2_sha512"])
        hashed_password_sha512 = passwords_sha512.make(plain_password)
        hashed_password_sha256 = passwords_sha256.make(plain_password)

        passwords = Passwords(["pbkdf2_sha256", "pbkdf2_sha512"])
        assert passwords.verify(plain_password, hashed_password_sha512)
        assert passwords.verify(plain_password, hashed_password_sha256)

    def test_needs_update(self) -> None:
        plain_password = "password"
        old_passwords = Passwords(["pbkdf2_sha256"])
        new_passwords = Passwords(
            ["pbkdf2_sha512", "pbkdf2_sha256"],
            deprecated=["pbkdf2_sha256"],
            default="pbkdf2_sha512",
        )

        password = old_passwords.make(plain_password)
        assert new_passwords.needs_update(password)

    async def test_verify_and_migrate(self) -> None:
        plain_password = "password"
        old_passwords = Passwords(["pbkdf2_sha256"])
        new_passwords = Passwords(
            ["pbkdf2_sha512", "pbkdf2_sha256"],
            deprecated=["pbkdf2_sha256"],
            default="pbkdf2_sha512",
        )

        password = old_passwords.make(plain_password)
        migrated, new_hash = new_passwords.verify_and_migrate(plain_password, password)
        assert migrated
        assert new_passwords.verify(plain_password, new_hash)

        migrated, new_hash = await new_passwords.averify_and_migrate(plain_password, password)
        assert migrated
        assert new_passwords.verify(plain_password, new_hash)
