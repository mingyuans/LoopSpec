"""LoopSpec: a gated artifact workflow CLI.

``__version__`` comes from the installed distribution's metadata, which the build
backend stamped from the git tag (see hatch_version.py). Nothing here declares a
version, so there is no second copy to drift out of sync with the tag.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

try:
    __version__ = _distribution_version("loopspec")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
