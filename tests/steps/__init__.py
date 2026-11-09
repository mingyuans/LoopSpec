"""Step definitions for the BDD scenarios in `tests/features`.

`tests/test_bdd.py` binds every feature file with `scenarios("features")`; the modules here
are registered as plugins through `pytest_plugins` in `tests/conftest.py`, so each step is
visible to every feature. `common.py` holds steps used by several features and
`<name>_steps.py` the steps of `features/<name>.feature`.

Because all steps are global, every (step type, step text/pattern) must be unique across this
package and no two patterns may match the same feature line; reword the step in both the
feature and here rather than relying on which definition pytest-bdd happens to pick.

Each feature carries a tag named after its file (`@version` in `version.feature`), registered
as a marker in `pyproject.toml`, so a single feature runs with `pytest tests/test_bdd.py -m
version`. A new feature needs both the tag and the marker entry.
"""
