.PHONY: install install-local dev test test-bdd test-llm docs-check build lint clean release-dry-run

install:
	uv sync

dev:
	uv run loopspec --help

# Everything except the `timing` tests runs in parallel with pytest-xdist (each test owns its
# tmp_path). Tests marked `timing` assert wall-clock budgets that a fully loaded machine can
# miss, so they run afterwards on their own, serially.
test:
	uv run pytest -v -n auto -m "not timing and not llm"
	uv run pytest -v -m "timing and not llm"

# Real-model end-to-end scenarios (tests/features/llm_skills.feature): every model start
# goes through tests/llm_launcher.py, which reads launcher/model/limits from the
# LOOPSPEC_LLM_* variables (default model claude-sonnet-5-5, never Opus). They cost money,
# so they never run in `make test`. A failing scenario is retried once, except a RED-LINE
# failure (the model broke the human-confirmation rule), which fails at once.
LLM_RUNS_DIR := $(CURDIR)/.llm-e2e-runs/$(shell date -u +%Y%m%dT%H%M%SZ)
test-llm:
	LOOPSPEC_LLM_E2E=1 LOOPSPEC_LLM_RUNS_DIR="$(LLM_RUNS_DIR)" \
		uv run pytest tests/test_bdd.py -m llm -n 4 --reruns 1 --rerun-except RED-LINE --rerun-except GUARD-BYPASS --rerun-except LLM-AUTH -v

# Only the BDD scenarios, in parallel.
test-bdd:
	uv run pytest tests/test_bdd.py -n auto -q

docs-check:
	uv run pytest tests/test_docs_consistency.py -v

lint:
	uv run ruff check src tests hatch_version.py
	uv run mypy src hatch_version.py

build:
	uv build

# Build the working tree and install the resulting wheel as the global `loopspec`
# command -- what install.sh does to a released wheel, done to local sources. It
# replaces whatever `uv tool` currently has installed, and an untagged tree
# installs as 0.0.0.dev0; set LOOPSPEC_BUILD_VERSION to stamp a real version.
# dist is cleared first so the wheel glob below can only resolve to this build.
install-local:
	rm -rf dist
	$(MAKE) build
	uv tool install --force dist/loopspec-*.whl

# Run the release checks that do not need CI. Pass TAG to build the artifacts that
# tag would publish and assert their filenames, before spending a real tag on it:
#   make release-dry-run TAG=v0.2.0
#   make release-dry-run TAG=v0.2.1-beta
# TAG_VERSION is the package version the tag publishes, the same mapping the
# release workflow applies: vX.Y.Z -> X.Y.Z, vX.Y.Z-beta -> X.Y.Zb0 (PEP 440's
# spelling of a bare beta, which is what hatchling names the artifacts after).
# Without TAG the build resolves to the dev version, which is what an untagged
# tree is supposed to produce.
TAG_BASE = $(patsubst v%,%,$(TAG))
TAG_VERSION = $(if $(filter %-beta,$(TAG_BASE)),$(patsubst %-beta,%b0,$(TAG_BASE)),$(TAG_BASE))

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
