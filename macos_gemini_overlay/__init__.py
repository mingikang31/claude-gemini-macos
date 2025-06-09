"""
macOS Claude Overlay - A macOS overlay app for Anthropic Claude.
"""

import os
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ABOUT_DIR = os.path.join(DIRECTORY, "about")
with open(os.path.join(ABOUT_DIR,"version.txt")) as f:
    __version__ = f.read().strip()
with open(os.path.join(ABOUT_DIR,"author.txt")) as f:
    __author__ = f.read().strip()

__all__ = ["main"]

# Lazily import the real CLI entry‐point to avoid importing it twice when
# executing with "python -m macos_claude_overlay.main" (runpy will import the
# module after the package has already been initialised).

def main(*args, **kwargs):  # noqa: D401 – simple wrapper
    """Entrypoint wrapper that defers the heavy import until needed."""
    from .main import main as _main  # local import to prevent early execution
    return _main(*args, **kwargs)
