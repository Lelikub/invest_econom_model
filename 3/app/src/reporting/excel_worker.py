"""Bounded child process: an actual Excel engine, never synthetic cached values."""
import sys
from pathlib import Path


def main():
    import pythoncom
    import win32com.client
    path=Path(sys.argv[1]).resolve()
    if not path.is_file(): raise FileNotFoundError(path)
    pythoncom.CoInitialize()
    app=None; book=None
    try:
        app=win32com.client.DispatchEx('Excel.Application')
        app.Visible=False
        app.DisplayAlerts=False
        app.AutomationSecurity=3
        book=app.Workbooks.Open(str(path),UpdateLinks=0,ReadOnly=False)
        app.CalculateFullRebuild()
        book.Save()
        print(f'EXCEL_RECALCULATED version={app.Version}')
    finally:
        if book is not None: book.Close(SaveChanges=False)
        if app is not None: app.Quit()
        pythoncom.CoUninitialize()


if __name__=='__main__': main()
