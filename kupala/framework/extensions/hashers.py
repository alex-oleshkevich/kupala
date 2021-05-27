from kupala.application import App
from kupala.contracts import PasswordHasher
from kupala.extensions import Extension
from kupala.utils import import_string


class HashingExtension(Extension):
    default_hashers = {
        "insecure": "kupala.security.hashers.InsecureHasher",
        "pbkdf2_sha256": "kupala.security.hashers.Pbkdf2Sha256Hasher",
        "pbkdf2_sha512": "kupala.security.hashers.Pbkdf2Sha512Hasher",
    }

    def __init__(
        self,
        hashers: dict[str, str] = None,
        default: str = "pbkdf2_sha256",
    ):
        self.default = default
        self.hashers = self.default_hashers
        if hashers:
            self.hashers.update(hashers)

    def register(self, app: App) -> None:
        for name, hasher in self.hashers.items():
            hasher_class = import_string(hasher)
            app.singleton(
                hasher_class,
                hasher_class,
                aliases=f"hasher.{name}",
                tags=["password_hasher"],
            )

        app.alias(f"hasher.{self.default}", PasswordHasher)
