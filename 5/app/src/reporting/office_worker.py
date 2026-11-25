"""Office automation runs in a child process so a COM failure is recoverable."""
import json
import os
from pathlib import Path
import sys
import traceback


def configure():
    import win32com.client
    return win32com.client.DispatchEx


def excel(path):
    import pythoncom
    app=configure()("Excel.Application")
    book=None
    solver=None
    try:
        app.Visible=False
        app.DisplayAlerts=False
        app.EnableEvents=False
        file=Path(app.LibraryPath)/"SOLVER"/"SOLVER.XLAM"
        if not file.is_file():
            raise FileNotFoundError(file)
        solver=app.Workbooks.Open(str(file), 0, True)
        book=app.Workbooks.Open(str(path),0,False)
        def run(proc,*args):
            return app.Run(f"'{solver.Name}'!{proc}",*args)
        statuses={}
        sensitivity=[]
        for name in ("LP","MILP","Fixed LP","Knapsack"):
            sheet=book.Worksheets(name)
            sheet.Activate()
            run("SolverReset")
            variables=("$B$2:$H$2" if name=="Knapsack" else "$B$2:$D$2" if name=="Fixed LP" else "$B$2:$G$2")
            sheet.Range(variables).Value=0
            run("SolverOk","$B$3",1,0,variables,2)
            gap_percent=book.Worksheets("Settings").Range("B8").Value*100
            missing=pythoncom.Missing
            run("SolverOptions",30,1000,1e-9,True,False,missing,missing,missing,gap_percent,True,missing,True)
            if name=="Knapsack":
                for addr,kind,rhs in (("$B$6",3,0),("$B$8",1,1),("$B$9",1,0),("$B$10",2,0),("$B$2:$H$2",5,None)):
                    run("SolverAdd",addr,kind,rhs if rhs is not None else missing)
            else:
                run("SolverAdd","$B$5:$B$9",1,"$C$5:$C$9")
                if name=="LP":
                    run("SolverAdd","$E$2:$G$2",1,1)
                elif name=="MILP":
                    run("SolverAdd","$E$2:$G$2",5,missing)
            status=int(run("SolverSolve",True))
            statuses[name]=status
            if status != 0:
                raise RuntimeError(f"Excel Solver {name}: {status}")
            before={ws.Name for ws in book.Worksheets}
            if name in {"LP","Fixed LP"}:
                run("SolverFinish",1,(2,))
                reports=[ws.Name for ws in book.Worksheets if ws.Name not in before]
                if len(reports)!=1:
                    raise RuntimeError(f"Excel Solver did not create a sensitivity report for {name}: {reports}")
                sensitivity.extend(reports)
            else:
                run("SolverFinish",1)
        app.CalculateFullRebuild()
        book.Save()
        return {"status":"PASS","statuses":statuses,"sensitivity_sheets":sensitivity,"excel_version":str(app.Version)}
    finally:
        if book is not None:
            book.Close(False)
        if solver is not None:
            solver.Close(False)
        app.Quit()


def documents(folder):
    dispatch=configure()
    word=dispatch("Word.Application")
    ppt=None
    counts={}
    dest=folder / "editor_previews"
    dest.mkdir(exist_ok=True)
    try:
        word.Visible=False
        word.DisplayAlerts=0
        for path in sorted(folder.glob("*.docx")):
            doc=word.Documents.Open(str(path),ReadOnly=True,AddToRecentFiles=False,Visible=False)
            try:
                doc.Repaginate()
                counts[path.name]=int(doc.ComputeStatistics(2))
                doc.ExportAsFixedFormat(str(dest/(path.stem+".pdf")),17)
            finally:
                doc.Close(False)
        ppt=dispatch("PowerPoint.Application")
        for path in sorted(folder.glob("*.pptx")):
            presentation=ppt.Presentations.Open(str(path),ReadOnly=True,Untitled=False,WithWindow=False)
            try:
                counts[path.name]=presentation.Slides.Count
                presentation.SaveAs(str(dest/(path.stem+".pdf")),32)
            finally:
                presentation.Close()
        return {"status":"OPENED_AND_RENDERED","page_counts":counts}
    finally:
        if ppt is not None:
            ppt.Quit()
        word.Quit()


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        command,path=sys.argv[1:]
        output={"excel":excel,"documents":documents}[command](Path(path).resolve())
        print(json.dumps(output,ensure_ascii=False))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
