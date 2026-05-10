from asgiref.typing import ASGI3Application, ASGIReceiveCallable, ASGISendCallable
from asgiref.typing import Scope as ASGIScope

type ASGIApp = ASGI3Application
type Receive = ASGIReceiveCallable
type Send = ASGISendCallable
type Scope = ASGIScope
type ASGIMiddleware = ASGIApp

__all__ = ["ASGIApp", "Receive", "Scope", "Send", "ASGIMiddleware"]
