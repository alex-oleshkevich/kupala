from kupala.testing import AsyncTestClient


async def test_welcome(client: AsyncTestClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
