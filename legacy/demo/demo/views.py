from kupala.requests import Request
from kupala.responses import JSONResponse, Response
from kupala.routing import RouteGroup
from redis import Redis

from demo.resources import templates
from demo.settings import settings

routes = RouteGroup()


@routes.get("/")
async def welcome_view(request: Request, dep: Redis) -> Response:
    print(dep)
    return templates.TemplateResponse(request, "welcome.html")


@routes.get("/health")
async def health_view(request: Request) -> Response:
    return JSONResponse(
        {
            "app_env": settings.app_env,
            "commit": settings.release_commit,
            "date": settings.release_date,
            "branch": settings.release_branch,
            "version": settings.release_version,
        }
    )
