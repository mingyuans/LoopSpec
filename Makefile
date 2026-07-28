.PHONY: install dev test build lint clean

install:
	uv sync

dev:
	uv run loopspec --help

test:
	uv run pytest -v

lint:
	uv run ruff check src tests
	uv run mypy src

build:
	uv build

clean:
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
