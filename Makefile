.PHONY: install dev test docs-check build lint clean release-dry-run

install:
	uv sync

dev:
	uv run loopspec --help

test:
	uv run pytest -v

docs-check:
	uv run pytest tests/test_docs_consistency.py -v

lint:
	uv run ruff check src tests scripts
	uv run mypy src

build:
	uv build

# Run the release checks that do not need CI. Pass TAG to also check that a tag
# name agrees with the two version declarations, before spending a real tag on it:
#   make release-dry-run TAG=v0.2.0
release-dry-run:
ifdef TAG
	python3 scripts/check_version.py --expect "$(patsubst v%,%,$(TAG))"
else
	python3 scripts/check_version.py
endif
	sh -n install.sh
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck install.sh && echo "shellcheck: clean"; \
	else \
		echo "shellcheck: not installed, skipped (it is mandatory in CI)"; \
	fi
	uv build

clean:
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
