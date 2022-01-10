from __future__ import annotations

from kupala.application import get_current_application


def make_password(raw_password: str) -> str:
    return get_current_application().passwords.hash(raw_password)


def check_password(raw_password: str, hashed_password: str) -> bool:
    return get_current_application().passwords.verify(raw_password, hashed_password)
