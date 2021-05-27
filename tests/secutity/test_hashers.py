from kupala.security.hashers import InsecureHasher


def test_insecure_hasher():
    hasher = InsecureHasher()
    assert hasher.hash("password") == "password"
    assert hasher.verify("password", "password") is True
    assert hasher.needs_update("password") is False
