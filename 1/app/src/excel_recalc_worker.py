"""Short-lived Microsoft Excel COM worker used by :mod:`excel_builder`."""

from __future__ import annotations

import gc
import site
import sys
from pathlib import Path


def _add_local_dependencies() -> None:
    local_packages = Path(__file__).resolve().parents[1] / ".python-packages"
    if local_packages.is_dir():
        site.addsitedir(str(local_packages))


def recalculate(path: Path) -> None:
    """Open, fully calculate, save, and close one workbook in Excel."""

    _add_local_dependencies()
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False
        workbook = excel.Workbooks.Open(str(path.resolve()), UpdateLinks=0, ReadOnly=False)
        excel.CalculateFullRebuild()
        workbook.Save()
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=True)
        if excel is not None:
            excel.Quit()
        workbook = None
        excel = None
        gc.collect()
        pythoncom.CoUninitialize()


def main(argv: list[str] | None = None) -> int:
    """Run the COM worker with a single workbook path."""

    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Ожидается один путь к XLSX", file=sys.stderr)
        return 2
    try:
        recalculate(Path(arguments[0]))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

