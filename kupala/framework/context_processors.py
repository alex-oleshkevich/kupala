from kupala.authentication import AuthState
from kupala.flashes import get_flash_messages
from kupala.requests import Request


def pass_old_input(request: Request) -> dict:
    return {
        "old_input": request.old_data(),
    }


def pass_errors(request: Request) -> dict:
    return {"errors": request.errors()}


def flash_messages(request: Request) -> dict:
    return {"flash_messages": get_flash_messages(request)}


def pass_auth(request: Request) -> dict:
    try:
        return {"auth": request.auth}
    except AssertionError:
        return {"auth": AuthState()}
