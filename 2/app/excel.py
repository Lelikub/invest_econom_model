"""Independent, cell-formula CRR ground truth and actual Excel reconciliation."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from model import ModelResult


INPUT_CELLS = {"I0": "B2", "S0": "B3", "K": "B4", "r": "B5", "sigma": "B6", "delta": "B7", "T": "B8", "N": "B9", "m": "B10"}
PARAM_CELLS = {"dt": "B2", "u": "B3", "d": "B4", "growth": "B5", "p": "B6", "discount_factor": "B7", "recombination": "B8", "no_arbitrage": "B9"}


def _col(j: int) -> str:
    from openpyxl.utils import get_column_letter
    return get_column_letter(j + 2)


def _style(ws) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 26
    for c in range(2, 35):
        ws.column_dimensions[_col(c-2)].width = 18
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="17365D")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True)


def build_ground_truth(result: ModelResult, path: Path, stress: list[dict], scenarios: list[dict]) -> dict[str, str]:
    from openpyxl import Workbook
    from openpyxl.workbook.properties import CalcProperties
    wb = Workbook()
    inputs = wb.active; inputs.title = "01_Inputs"
    inputs.append(["Parameter", "Value", "Unit", "Source page", "Description"])
    values = result.inputs
    units = {"I0":"USD million", "S0":"USD million", "K":"USD million", "r":"fraction/year", "sigma":"fraction/year", "delta":"fraction/year", "T":"years", "N":"steps", "m":"fraction"}
    for key in INPUT_CELLS:
        inputs.append([key, getattr(values,key), units[key], 5, key])
    params = wb.create_sheet("02_CRR_Parameters")
    params.append(["Parameter", "Formula/result", "Interpretation"])
    formulas = {
        "dt": "='01_Inputs'!B8/'01_Inputs'!B9",
        "u": "=EXP('01_Inputs'!B6*SQRT(B2))",
        "d": "=1/B3",
        "growth": "=EXP(('01_Inputs'!B5-'01_Inputs'!B7)*B2)",
        "p": "=(B5-B4)/(B3-B4)",
        "discount_factor": "=EXP(-'01_Inputs'!B5*B2)",
        "recombination": "=B3*B4",
        "no_arbitrage": '=IF(AND(B4<B5,B5<B3,B6>0,B6<1),"PASS","FAIL")',
    }
    for key, formula in formulas.items():
        params.append([key, formula, "Independent Excel formula"])
    assets = wb.create_sheet("03_S_Lattice")
    options = wb.create_sheet("04_C_Lattice")
    asset_refs = {}; option_refs = {}
    assets.cell(1,1,"i / j")
    options.append(["i", "j", "S", "Intrinsic", "Continuation", "C", "Decision"])
    for j in range(values.N+1):
        assets.cell(1,j+2,j)
    for i in range(values.N+1):
        assets.cell(i+2,1,i)
        for j in range(i+1):
            c = f"{_col(j)}{i+2}"
            assets[c] = f"='01_Inputs'!$B$3*'01_Inputs'!$B$10*'02_CRR_Parameters'!$B$3^{j}*'02_CRR_Parameters'!$B$4^{i-j}"
            asset_refs[(i,j)] = f"'03_S_Lattice'!{c}"
    # Rows are chronological, but forward references permit Excel to solve
    # backward induction without importing any Python-calculated values.
    for i in range(values.N+1):
        for j in range(i+1):
            row = options.max_row+1
            option_refs[(i,j)] = f"'04_C_Lattice'!F{row}"
            options.cell(row,1,i); options.cell(row,2,j)
            options.cell(row,3,f"={asset_refs[(i,j)]}")
            options.cell(row,4,f"=MAX(C{row}-'01_Inputs'!$B$4,0)")
            if i == values.N:
                options.cell(row,5,"=0")
                options.cell(row,6,f"=D{row}")
                options.cell(row,7,'="EXPIRY"')
            else:
                # Fill child references after the table has been laid out.
                options.cell(row,5,f"=CHILDREN_{i}_{j}")
                options.cell(row,6,f"=MAX(D{row},E{row})")
                options.cell(row,7,f'=IF(D{row}>E{row},"EXERCISE","WAIT")')
    for (i,j), ref in option_refs.items():
        if i == values.N:
            continue
        row = int(ref.split("F")[-1])
        down = option_refs[(i+1,j)]
        up = option_refs[(i+1,j+1)]
        options.cell(row,5,f"='02_CRR_Parameters'!$B$7*((1-'02_CRR_Parameters'!$B$6)*{down}+'02_CRR_Parameters'!$B$6*{up})")
    summary = wb.create_sheet("05_Strategic_NPV")
    summary.append(["Metric", "Excel formula"])
    summary.append(["NPV_trad", "='01_Inputs'!B3-'01_Inputs'!B2"])
    summary.append(["ROV", f"={option_refs[(0,0)]}"])
    summary.append(["NPV_strat", "=B2+B3"])
    sh_stress = wb.create_sheet("06_Stress_Tests")
    sh_stress.append(["Test", "Status", "ROV", "NPV_strat", "Details", "Origin"])
    for row in stress:
        sh_stress.append([row.get("test"),row.get("status"),row.get("rov"),row.get("npv_strat"),row.get("details"),"Python stress execution"])
    verify = wb.create_sheet("07_Verification")
    verify.append(["Metric", "Python value", "Excel formula", "Absolute error", "Status"])
    for metric, py_value, excel_ref in _metrics(result, asset_refs, option_refs):
        row = verify.max_row+1
        verify.append([metric,py_value,f"={excel_ref}",f"=ABS(B{row}-C{row})",f'=IF(D{row}<=1E-8,"PASS","FAIL")'])
    sh_scen = wb.create_sheet("08_Scenarios")
    sh_scen.append(["Metric", "Base", "Shock 70%", "Change", "Origin"])
    for row in scenarios:
        sh_scen.append([row["metric"],row["base"],row["shock"],row["absolute_change"],"Python scenario execution"])
    for ws in wb:
        _style(ws)
    wb.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True, forceFullCalc=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    wb.save(path)
    return {name: ref for name, _, ref in _metrics(result, asset_refs, option_refs)}


def _metrics(result, asset_refs, option_refs):
    p=result.params
    rows=[(key,getattr(p,key),f"'02_CRR_Parameters'!{PARAM_CELLS[key]}") for key in ("dt","u","d","p","discount_factor")]
    rows += [(f"S[{i},{j}]",result.asset[i][j],ref) for (i,j),ref in asset_refs.items()]
    rows += [(f"C[{i},{j}]",result.option[i][j].C,ref) for (i,j),ref in option_refs.items()]
    rows += [("NPV_trad",result.npv_trad,"'05_Strategic_NPV'!B2"),("ROV",result.rov,"'05_Strategic_NPV'!B3"),("NPV_strat",result.npv_strat,"'05_Strategic_NPV'!B4")]
    return rows


def recalculate_with_excel(path: Path) -> None:
    """Require a real Excel calculation; never fill cached values ourselves."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = None
    try:
        app = win32com.client.DispatchEx("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        book = app.Workbooks.Open(str(path.resolve()))
        try:
            app.CalculateFullRebuild()
            book.Save()
        finally:
            book.Close(SaveChanges=False)
    finally:
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def reconcile(result: ModelResult, path: Path, out: Path) -> list[dict]:
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=True)
    refs = {}
    for key in ("dt","u","d","p","discount_factor"):
        refs[key] = wb["02_CRR_Parameters"][PARAM_CELLS[key]].value
    for i in range(result.inputs.N+1):
        for j in range(i+1):
            refs[f"S[{i},{j}]"] = wb["03_S_Lattice"][f"{_col(j)}{i+2}"].value
            row = 2+i*(i+1)//2+j
            refs[f"C[{i},{j}]"] = wb["04_C_Lattice"][f"F{row}"].value
    for metric,row in (("NPV_trad",2),("ROV",3),("NPV_strat",4)):
        refs[metric] = wb["05_Strategic_NPV"][f"B{row}"].value
    py = {key:getattr(result.params,key) for key in ("dt","u","d","p","discount_factor")}
    py.update({f"S[{i},{j}]":v for i,row in enumerate(result.asset) for j,v in enumerate(row)})
    py.update({f"C[{i},{j}]":n.C for i,row in enumerate(result.option) for j,n in enumerate(row)})
    py.update({"NPV_trad":result.npv_trad,"ROV":result.rov,"NPV_strat":result.npv_strat})
    records=[]
    for metric,value in py.items():
        other=refs[metric]
        valid=isinstance(other,(int,float)) and math.isfinite(other)
        error=abs(value-other) if valid else ""
        rel=error/max(1,abs(value),abs(other)) if valid else ""
        status=("PASS" if math.isclose(value,other,rel_tol=1e-8,abs_tol=1e-8) else "FAIL") if valid else "NOT_VERIFIED"
        records.append({"metric":metric,"node":metric if "[" in metric else "","python_value":value,"excel_value":other if valid else "","absolute_error":error,"relative_error":rel,"tolerance":1e-8,"status":status})
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=records[0].keys());writer.writeheader();writer.writerows(records)
    return records
