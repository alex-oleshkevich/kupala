[working-directory("demo")]
dev:
    uv run -- uvicorn --port 7000 --reload demo.app:app
