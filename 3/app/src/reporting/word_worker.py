"""Optional real Word rendering for internal layout inspection."""
from pathlib import Path
import sys


def main():
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize(); app=None; doc=None
    try:
        app=win32com.client.DispatchEx('Word.Application')
        app.Visible=False; app.DisplayAlerts=0; app.AutomationSecurity=3
        doc=app.Documents.Open(str(Path(sys.argv[1]).resolve()),ReadOnly=True,AddToRecentFiles=False)
        doc.ExportAsFixedFormat(str(Path(sys.argv[2]).resolve()),17,OpenAfterExport=False)
        print('WORD_RENDERED')
    finally:
        if doc is not None: doc.Close(SaveChanges=0)
        if app is not None: app.Quit(SaveChanges=0)
        pythoncom.CoUninitialize()


if __name__=='__main__': main()
