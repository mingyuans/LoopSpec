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
	uv run ruff check src tests hatch_version.py
	uv run mypy src hatch_version.py

build:
	uv build

# Run the release checks that do not need CI. Pass TAG to build the artifacts that
# tag would publish and assert their filenames, before spending a real tag on it:
#   make release-dry-run TAG=v0.2.0
# Without TAG the build resolves to the dev version, which is what an untagged
# tree is supposed to produce.
TAG_VERSION = $(patsubst v%,%,$(TAG))

release-dry-run:
	sh -n install.sh
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck install.sh && echo "shellcheck: clean"; \
	else \
		echo "shellcheck: not installed, skipped (it is mandatory in CI)"; \
	fi
	rm -rf dist
ifdef TAG
	LOOPSPEC_BUILD_VERSION="$(TAG_VERSION)" uv build
	@for asset in "dist/loopspec-$(TAG_VERSION)-py3-none-any.whl" "dist/loopspec-$(TAG_VERSION).tar.gz"; do \
		[ -f "$$asset" ] || { echo "error: $(TAG) would not produce $$asset"; exit 1; }; \
	done
	@echo "artifacts match $(TAG)"
else
	uv build
endif

clean:
	rm -rf dist build *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
