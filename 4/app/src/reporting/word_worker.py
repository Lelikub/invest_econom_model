"""Render DOCX through installed Word, without saving changes to the source DOCX."""
from pathlib import Path
import sys

def main():
    import pythoncom
    import win32com.client
    source=Path(sys.argv[1]).resolve(); target=Path(sys.argv[2]).resolve()
    pythoncom.CoInitialize(); word=None; document=None
    try:
        word=win32com.client.DispatchEx('Word.Application')
        word.Visible=False; word.DisplayAlerts=0; word.AutomationSecurity=3
        document=word.Documents.Open(str(source),ConfirmConversions=False,ReadOnly=True,AddToRecentFiles=False)
        document.Repaginate()
        document.ExportAsFixedFormat(str(target),17,OpenAfterExport=False)
        print(f'WORD_PDF_RENDERED pages={document.ComputeStatistics(2)} version={word.Version}',flush=True)
    finally:
        if document is not None: document.Close(SaveChanges=0)
        if word is not None: word.Quit(SaveChanges=0)
        pythoncom.CoUninitialize()

if __name__=='__main__': main()
