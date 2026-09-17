"""Portable test runner for environments whose Python ignores PYTHONPATH."""

from __future__ import annotations

import site
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
LOCAL_PACKAGES = APP_DIR / ".python-packages"
sys.path.insert(0, str(APP_DIR))
if LOCAL_PACKAGES.is_dir():
    site.addsitedir(str(LOCAL_PACKAGES))

import pytest


def build_pytest_args() -> list[str]:
    """Keep all pytest-generated files within the application directory."""

    return [
        str(APP_DIR / "tests"),
        "-v",
        "-o",
        f"cache_dir={APP_DIR / '.pytest_cache'}",
        f"--basetemp={APP_DIR / '.test-tmp'}",
    ]


if __name__ == "__main__":
    raise SystemExit(pytest.main(build_pytest_args()))

