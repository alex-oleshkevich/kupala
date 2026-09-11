[working-directory("demo")]
dev:
    uv run -- uvicorn --port 7000 --reload demo.app:app

test *args:
    uv run pytest {{ args }}

test-pkg pkg *args:
    uv run pytest packages/{{ pkg }}/tests {{ args }}

testc *args:
    uv run pytest --cov --cov-report=term-missing --cov-fail-under=100 {{ args }}

check:
    prek run --all-files

verify: check
    uv run mypy
    uv run pytest --cov --cov-report=term-missing --cov-fail-under=100
    uv build --all-packages --no-sources
    git diff --check

[working-directory("demo")]
cli *args:
    uv run -- kupala {{ args }}
