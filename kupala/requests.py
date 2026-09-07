from starlette.requests import Request as BaseRequest


class Request(BaseRequest):
    pass


__all__ = ["Request"]
