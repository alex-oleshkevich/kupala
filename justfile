[working-directory("demo")]
dev:
    uv run -- uvicorn --port 7000 --reload demo.app:app

test *args:
    uv run pytest {{ args }}

testc *args:
    uv run pytest --cov --cov-report=term-missing --cov-fail-under=100 {{ args }}

check:
    prek run --all-files
