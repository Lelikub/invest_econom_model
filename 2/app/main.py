"""One-command ROA practical-work pipeline."""
from __future__ import annotations

import logging
import site
import subprocess
import sys
from pathlib import Path

APP=Path(__file__).resolve().parent
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
LOCAL=APP/".python-packages"
if LOCAL.is_dir():site.addsitedir(str(LOCAL))
# The previous practical-work workspace contains locally installed wheels in
# this managed environment. Ordinary users install requirements.txt instead.
SIBLING=APP.parent.parent/"1"/"app"/".python-packages"
if SIBLING.is_dir():site.addsitedir(str(SIBLING))

from analysis import plot_tree, scenario_comparison, sensitivity, stress_tests
from excel import build_ground_truth, recalculate_with_excel, reconcile
from model import calculate
from reporting import harness, report_data, write_markdown, write_word
from source import extract_pdf, parse_inputs


def setup_logger(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    logger=logging.getLogger("roa_pipeline");logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler=logging.FileHandler(path,mode="w",encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def main() -> int:
    output=APP/"output";output.mkdir(exist_ok=True)
    logs=APP/"logs";logger=setup_logger(logs/"pipeline.log")
    pdf=next((APP.parent/"data").glob("Задание*.pdf"),None)
    template=next((APP.parent/"data").glob("Шаблон*.docx"),None)
    issues=[]
    try:
        if pdf is None or template is None:raise FileNotFoundError("Assignment PDF or Word template missing")
        logger.info("STEP 01 | source files validated | pdf=%s | template=%s",pdf,template)
        pages=extract_pdf(pdf);logger.info("STEP 02 | PDF parsed | pages=%d",len(pages))
        source_csv=APP/"data"/"source_data.csv"
        data=parse_inputs(pages,pdf,source_csv)
        logger.info("STEP 03-07 | inputs extracted, exported, reloaded, validated | %s",data)
        base=calculate(data);logger.info("STEP 08-14 | CRR, arbitrage, NPV and lattice | ROV=%.10f | NPV_strat=%.10f",base.rov,base.npv_strat)
        shock=calculate(data.changed(sigma=.7))
        stress=stress_tests(data)
        for row in stress:
            logger.info("STEP 19-20 | stress | %s | %s | %s",row["test"],row["status"],row["details"])
            if row["status"]!="PASS":issues.append({"stage":"stress","category":"model limitation","sheet":"Assumptions","issue":row["details"],"action_taken":"No extrapolated ROV reported","status":row["status"]})
        scenario=scenario_comparison(base,shock,output/"scenario_comparison.csv")
        sens=sensitivity(data,output/"sensitivity.csv")
        logger.info("STEP 21-25 | shock, sensitivity, audit, holding and bankability analysis completed")
        workbook=output/"Ground_Truth_ROA.xlsx"
        build_ground_truth(base,workbook,stress,scenario)
        logger.info("STEP 15 | formula Ground Truth created | %s",workbook)
        try:
            recalculate_with_excel(workbook)
            logger.info("STEP 16 | actual Microsoft Excel recalculation completed")
        except Exception as exc:
            message=f"Excel COM recalculation unavailable: {type(exc).__name__}: {exc}"
            logger.warning("STEP 16 | %s",message)
            issues.append({"stage":"Excel","category":"verification limitation","sheet":"Errors","issue":message,"action_taken":"Retained formulas; marked values NOT_VERIFIED","status":"WARNING"})
        recon=reconcile(base,workbook,output/"excel_python_reconciliation.csv")
        logger.info("STEP 17 | reconciliation | PASS=%d | FAIL=%d | NOT_VERIFIED=%d",sum(r["status"]=="PASS" for r in recon),sum(r["status"]=="FAIL" for r in recon),sum(r["status"]=="NOT_VERIFIED" for r in recon))
        for r in recon:
            if r["status"]=="FAIL":issues.append({"stage":"reconciliation","category":"numeric mismatch","sheet":"Errors","issue":f"{r['metric']}: Python={r['python_value']}, Excel={r['excel_value']}","action_taken":"Investigate formula and source","status":"FAIL"})
        test_run=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(APP/"tests"),"-v"],cwd=APP,capture_output=True,text=True,encoding="utf-8",errors="replace")
        (logs/"test_results.txt").write_text(test_run.stdout+test_run.stderr,encoding="utf-8")
        test_status="PASS" if test_run.returncode==0 else "FAIL"
        logger.info("STEP 18 | unit tests | %s | exit=%s",test_status,test_run.returncode)
        if test_status=="FAIL":issues.append({"stage":"unit tests","category":"test failure","sheet":"Errors","issue":"Unit test suite failed; see logs/test_results.txt","action_taken":"Review failing tests","status":"FAIL"})
        plot_tree(base,output/"crr_tree_base.png");plot_tree(shock,output/"crr_tree_sigma_70.png")
        logger.info("STEP 22 | CRR decision trees generated")
        issues.append({"stage":"source reference","category":"reference discrepancy","sheet":"Source_Issues","issue":f"PDF p.8 cites ROV=35.85; full-precision model gives {base.rov:.8f}; ordinary two-decimal rounding gives 35.86","action_taken":"Preserved full precision and disclosed unexplained 0.00992 difference","status":"WARNING"})
        harness(output/"HARNESS_LOG.xlsx",recon,stress,issues,test_status)
        logger.info("STEP 26 | Harness Log written")
        info=report_data(base,shock,recon,stress,sens,issues,test_status)
        write_markdown(output/"FINAL_REPORT.md",info)
        logger.info("STEP 27 | Markdown report written")
        word=output/"Итоговый_отчет_Практическая_работа_2_ФИП.docx"
        write_word(template,word,info,output/"crr_tree_base.png",output/"crr_tree_sigma_70.png")
        logger.info("STEP 28-29 | template Word report generated and validated | %s",word)
        required=[source_csv,workbook,output/"HARNESS_LOG.xlsx",output/"excel_python_reconciliation.csv",output/"scenario_comparison.csv",output/"crr_tree_base.png",output/"crr_tree_sigma_70.png",output/"FINAL_REPORT.md",word,logs/"pipeline.log"]
        if any(not p.is_file() or p.stat().st_size==0 for p in required):raise RuntimeError("Artifact integrity check failed")
        logger.info("STEP 30 | artifact integrity check passed | count=%d",len(required))
        print(f"ROV={base.rov:.6f}; NPV_trad={base.npv_trad:.6f}; NPV_strat={base.npv_strat:.6f}; shock_ROV={shock.rov:.6f}")
        print(f"Excel reconciliation: {sum(r['status']=='PASS' for r in recon)} PASS, {sum(r['status']=='FAIL' for r in recon)} FAIL, {sum(r['status']=='NOT_VERIFIED' for r in recon)} NOT_VERIFIED")
        print(f"Unit tests: {test_status}; Word: {word}")
        return 0 if test_status=="PASS" and not any(r["status"]=="FAIL" for r in recon) else 1
    except Exception:
        logger.exception("FATAL | pipeline failed")
        raise


if __name__=="__main__":raise SystemExit(main())
