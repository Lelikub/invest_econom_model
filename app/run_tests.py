"""Portable test runner for environments whose Python ignores PYTHONPATH."""

from __future__ import annotations

import site
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = APP_DIR.parent
LOCAL_PACKAGES = APP_DIR / ".python-packages"
sys.path.insert(0, str(REPOSITORY_ROOT))
if LOCAL_PACKAGES.is_dir():
    site.addsitedir(str(LOCAL_PACKAGES))

import pytest


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(APP_DIR / "tests"), "-v"]))

