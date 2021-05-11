import datetime
from dataclasses import dataclass

from starlette import requests


class Request(requests.Request):
    pass


@dataclass
class RequestStarted:
    request: Request
    start_time: datetime.datetime


@dataclass
class RequestSuccess:
    request: Request
    end_time: datetime.datetime
    duration: float


@dataclass
class RequestCompleted:
    request: Request
    end_time: datetime.datetime
    duration: float


@dataclass
class RequestErrored:
    request: Request
    exception: Exception
    end_time: datetime.datetime
    duration: float
