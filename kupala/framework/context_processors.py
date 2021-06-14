from kupala.flashes import get_flash_messages
from kupala.requests import Request


def pass_old_input(request: Request) -> dict:
    data = request.old_data()
    return {
        "old": lambda k: data.get(k, ""),
        "old_input": data,
    }


def pass_errors(request: Request) -> dict:
    return {"errors": request.errors()}


def flash_messages(request: Request) -> dict:
    return {"flash_messages": get_flash_messages(request)}
