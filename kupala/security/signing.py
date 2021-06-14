from itsdangerous import TimestampSigner


def sign(text: str, secret_key: str) -> str:
    signer = TimestampSigner(secret_key)
    return signer.sign(text).decode()


def unsign(value: str, ttl: int, secret_key: str) -> str:
    signer = TimestampSigner(secret_key)
    return signer.unsign(value, ttl).decode()
