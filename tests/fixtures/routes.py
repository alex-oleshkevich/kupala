from kupala.routing import Routes


def configure(routes: Routes) -> None:
    routes.get("/", lambda: None)
