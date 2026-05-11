[working-directory("demo/")]
demo:
    uv run uvicorn --reload --port 7000 demo.app:app
