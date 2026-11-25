from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

from openpyxl import Workbook

from ..reporting.excel import format_book,sheet
from ..repositories import write_csv

MOSCOW=timezone(timedelta(hours=3))


def timestamp():
    return datetime.now(MOSCOW).isoformat(timespec="seconds")


class Harness:
    def __init__(self,app,logs,output):
        self.app=app
        self.logs=logs
        self.output=output
        self.events=[]
        self.errors=[]
        self.tests=[]
        self.reconciliation=[]
        self.fixes=[]
        self.assumptions=[]
        self.source_issues=self.read_source_issues(app/"docs/SOURCE_ISSUES.md")
        for p in ("events.jsonl","execution.log"):
            (logs/p).write_text("",encoding="utf-8")

    @staticmethod
    def read_source_issues(path):
        rows=[]
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("| SRC_"):
                code,page,observed,decision=(s.strip() for s in line.strip("|").split("|"))
                rows.append(dict(id=code,source=page,observed=observed,decision=decision,status="DOCUMENTED"))
        return rows

    def emit(self,stage,status,artifact="",detail=""):
        event=dict(date=timestamp(),stage=stage,status=status,artifact=artifact,detail=detail)
        self.events.append(event)
        with (self.logs/"events.jsonl").open("a",encoding="utf-8") as file:
            file.write(json.dumps(event,ensure_ascii=False)+"\n")
        with (self.logs/"execution.log").open("a",encoding="utf-8") as file:
            file.write(f'{event["date"]} | {stage} | {status} | {artifact} | {detail}\n')

    def error(self,stage,error):
        self.errors.append(dict(code=type(error).__name__,stage=stage,time=timestamp(),expected="Stage passes",
                                observed=str(error),traceback=traceback.format_exc()))

    def run_tests(self):
        env={**os.environ,"PYTHONPATH":os.pathsep.join((str(self.app),str(self.app/".deps"))),
             "PYTHONDONTWRITEBYTECODE":"1","PYTHONIOENCODING":"utf-8"}
        command=[sys.executable,"-m","unittest","discover","-s",str(self.app/"tests"),"-v"]
        result=subprocess.run(command,cwd=self.app,env=env,capture_output=True,encoding="utf-8",errors="replace",timeout=90)
        text=result.stdout+result.stderr
        (self.logs/"tests.log").write_text(text,encoding="utf-8")
        for line in text.splitlines():
            m=re.match(r"(test_\w+) \(([^)]*)\) \.\.\. (.+)",line)
            if m:
                test,name,outcome=m.groups()
                self.tests.append(dict(test=test,case=name,status="PASS" if outcome=="ok" else "FAIL",observed=outcome))
        if result.returncode or len([r for r in self.tests if r["status"]=="PASS"])<16:
            raise RuntimeError("Test runner failed or missed required tests; see logs/tests.log")
        return len(self.tests)

    def export(self):
        history=self.app/"docs/development_observations.json"
        observations=json.loads(history.read_text(encoding="utf-8")) if history.exists() else []
        errors=[*self.errors,*observations]
        fixes=self.fixes+[dict(code=o["code"],fix=o["fix"],retest=o["retest"]) for o in observations if o.get("fix")]
        groups={
            "Summary": list(self.events),
            "Errors": errors or [dict(status="NO_RECORDED_ERRORS")],
            "Source_Issues": self.source_issues,
            "Tests": self.tests or [dict(status="NOT_RUN")],
            "Reconciliation": self.reconciliation or [dict(status="NOT_RUN")],
            "Fixes": fixes or [dict(status="NO_RECORDED_FIXES")],
            "Assumptions": self.assumptions or [dict(status="NONE")],
        }
        wb=Workbook()
        wb.remove(wb.active)
        flat=[]
        for group,rows in groups.items():
            columns=list(dict.fromkeys(key for row in rows for key in row))
            sheet(wb,group,[columns]+[[row.get(key) for key in columns] for row in rows])
            flat.extend(dict(section=group,**row) for row in rows)
        format_book(wb)
        wb.save(self.output/"HARNESS_LOG.xlsx")
        write_csv(self.output/"HARNESS_LOG.csv",flat)
