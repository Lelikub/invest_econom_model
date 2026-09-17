"""Tests for the portable test runner configuration."""

from pathlib import Path

from run_tests import build_pytest_args


def test_runner_keeps_pytest_cache_inside_application_directory():
    app_dir = Path(__file__).resolve().parents[1]

    assert f"cache_dir={app_dir / '.pytest_cache'}" in build_pytest_args()


def test_runner_keeps_temporary_files_inside_application_directory():
    app_dir = Path(__file__).resolve().parents[1]

    assert f"--basetemp={app_dir / '.test-tmp'}" in build_pytest_args()
