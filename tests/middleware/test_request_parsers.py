import pytest

from kupala.http import JSONResponse, Request, Routes, UnsupportedMediaType
from kupala.http.exceptions import RequestTimeout, RequestTooLarge
from kupala.http.middleware import Middleware
from kupala.http.middleware.request_parser import RequestParserMiddleware
from kupala.http.request_parsers import JSONParser, MultipartParser, URLEncodedParser
from kupala.testclient import TestClient
from tests.conftest import TestAppFactory


@pytest.mark.asyncio
async def test_parses_urlencoded(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse(dict(request.data))  # type: ignore

    routes.add('/', view, methods=['POST'])
    app = test_app_factory(
        middleware=[Middleware(RequestParserMiddleware, parsers=['urlencoded'])],
        routes=routes,
    )

    client = TestClient(app)
    assert client.post('/', data={'status': 'success'}).json() == {'status': 'success'}


@pytest.mark.asyncio
async def test_parses_multipart(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        data = request.data.get('file')
        assert data
        return JSONResponse(
            {
                'filename': data.filename,
                'content': await data.read(),
            }
        )

    routes.add('/', view, methods=['POST'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['multipart'])],
    )

    client = TestClient(app)
    assert client.post(
        '/',
        files=[
            ('file', ('file.txt', b'content', 'text/plain')),
        ],
    ).json() == {'filename': 'file.txt', 'content': 'content'}


@pytest.mark.asyncio
async def test_parses_json(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse(dict(request.data))  # type: ignore

    routes.add('/', view, methods=['POST'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json'])],
    )

    client = TestClient(app)
    assert client.post('/', json={'status': 'success'}).json() == {'status': 'success'}


@pytest.mark.asyncio
async def test_raises_for_unsupported_mime(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse(dict(request.data))  # type: ignore

    routes.add('/', view, methods=['POST'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json'])],
    )

    client = TestClient(app)
    with pytest.raises(UnsupportedMediaType, match='No parser configured to parse "text/plain" type.'):
        assert client.post('/', headers={'content-type': 'text/plain'})


@pytest.mark.asyncio
async def test_mime_whitelist_passthrough(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse(await request.body())

    routes.add('/', view, methods=['POST'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json'], passthrough=['text/plain'])],
    )

    client = TestClient(app)
    assert client.post('/', data='content', headers={'content-type': 'text/plain'}).json() == 'content'


@pytest.mark.asyncio
async def test_mime_whitelist_passthrough_regex(test_app_factory: TestAppFactory, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse(await request.body())

    routes.add('/', view, methods=['POST'])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json'], passthrough=[r'text/*'])],
    )

    client = TestClient(app)
    assert client.post('/', data='content', headers={'content-type': 'text/plain'}).json() == 'content'


@pytest.mark.asyncio
async def test_urlencoded_request_limit(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        middleware=[Middleware(RequestParserMiddleware, parsers=[URLEncodedParser(max_length=2)])],
    )

    client = TestClient(app)
    with pytest.raises(RequestTooLarge, match='Request is too large. Read: 12, limit 2.'):
        assert client.post('/', data={'data': 'content'})


@pytest.mark.asyncio
async def test_multipart_request_limit(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        middleware=[Middleware(RequestParserMiddleware, parsers=[MultipartParser(max_length=2)])],
    )

    client = TestClient(app)
    with pytest.raises(RequestTooLarge, match='Request is too large. Read: 177, limit 2.'):
        assert client.post(
            '/',
            files=[
                ('file', ('file.txt', b'content', 'text/plain')),
            ],
        )


@pytest.mark.asyncio
async def test_json_request_limit(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        middleware=[Middleware(RequestParserMiddleware, parsers=[JSONParser(max_length=2)])],
    )

    client = TestClient(app)
    with pytest.raises(RequestTooLarge, match='Request is too large. Read: 19, limit 2.'):
        assert client.post('/', json={'data': 'content'})


@pytest.mark.asyncio
async def test_global_request_limit(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        middleware=[Middleware(RequestParserMiddleware, parsers=['json', 'multipart', 'urlencoded'], max_length=2)],
    )

    client = TestClient(app)
    with pytest.raises(RequestTooLarge, match='Request is too large. Read: 19, limit 2.'):
        assert client.post('/', json={'data': 'content'})

    with pytest.raises(RequestTooLarge, match='Request is too large. Read: 177, limit 2.'):
        assert client.post(
            '/',
            files=[
                ('file', ('file.txt', b'content', 'text/plain')),
            ],
        )
    with pytest.raises(RequestTooLarge, match='Request is too large. Read: 12, limit 2.'):
        assert client.post('/', data={'data': 'content'})


@pytest.mark.asyncio
async def test_read_timeout(test_app_factory: TestAppFactory) -> None:
    app = test_app_factory(
        middleware=[Middleware(RequestParserMiddleware, parsers=['json'], read_timeout=0.00001)],
    )

    client = TestClient(app)
    with pytest.raises(RequestTimeout, match='Did not complete request parsing after'):
        assert client.post('/', json={'data': 'content'})


@pytest.mark.asyncio
async def test_raises_for_invalid_alias(test_app_factory: TestAppFactory) -> None:
    with pytest.raises(KeyError, match='Unknown parser alias: jsoned. Choose from: multipart, urlencoded, json.'):
        test_app_factory(middleware=[Middleware(RequestParserMiddleware, parsers=['jsoned'], read_timeout=0.00001)])


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['GET', 'OPTIONS'])
async def test_ignores_methods(test_app_factory: TestAppFactory, method: str, routes: Routes) -> None:
    async def view(request: Request) -> JSONResponse:
        return JSONResponse('body_params' in request.scope)

    routes.add('/', view, methods=[method])
    app = test_app_factory(
        routes=routes,
        middleware=[Middleware(RequestParserMiddleware, parsers=['json'])],
    )

    client = TestClient(app)
    callback = getattr(client, method.lower())
    assert callback('/', json={}).json() is False
