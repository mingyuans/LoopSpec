"""Every BDD scenario under `tests/features`, bound in one place.

The step definitions live in `tests/steps` and are registered globally through
`pytest_plugins` in `tests/conftest.py`; see `tests/steps/__init__.py` for the layout.
"""

from pytest_bdd import scenarios

scenarios("features")
