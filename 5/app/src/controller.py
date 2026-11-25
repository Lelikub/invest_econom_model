from importlib.metadata import version
from hashlib import sha1
import os
from pathlib import Path
import platform
import re
from shutil import copyfile,rmtree
import subprocess
import traceback
from uuid import uuid4

from .calculators.certificates import CbcCertificate
from .calculators.operations import TOL
from .calculators.optimizer import ProductionAndPortfolioOptimizer
from .reporting.audit import ARCHIVE, audit_reports, json_to, package, render_office, sha
from .reporting.charts import ChartService
from .reporting.documents import ReportService
from .reporting.excel import WorkbookService, numerical_row
from .reporting.presentation import SlideDeck
from .reporting.tables import ResultTables
from .repositories import DataRepository, write_csv
from .services.analysis import ParetoAnalysis, ScenarioAnalysis, ids
from .services.brief import prepare_brief
from .services.harness import Harness,timestamp
from .services.inputs import DataValidationService, PdfExtractor, LECTURE_NAME, TEMPLATE_NAME


class PipelineController:
    def __init__(self,app):
        self.app=app
        self.logs=app/"logs"
        self.data=app/"data"

    def source(self,original,portable):
        file=original if original.is_file() else portable
        if not file.is_file():
            return None
        if file!=portable and (not portable.is_file() or sha(file)!=sha(portable)):
            copyfile(file,portable)
        return file

    def metadata(self,pdf,lecture,template):
        git=subprocess.run(["git","rev-parse","HEAD"],cwd=self.app,capture_output=True,text=True,timeout=10) if self.app.parent.parent.joinpath(".git").exists() else None
        sources={}
        for key,path in (("assignment",pdf),("lecture9",lecture),("word_template",template)):
            if path:
                sources[key]={"path":os.path.relpath(path,self.app).replace(os.sep,"/"),"sha256":sha(path)}
        return dict(started=timestamp(),base_commit=git.stdout.strip() if git and git.returncode==0 else None,
                    sources=sources,python=platform.python_version(),
                    dependencies={name:version(name) for name in ("scipy","PuLP","PyMuPDF","openpyxl","python-docx","matplotlib","python-pptx")},
                    solver={"primary":"SciPy HiGHS (linprog highs-ds and milp)","independent":"PuLP CBC",
                            "highs":self.highs_version()})

    @staticmethod
    def highs_version():
        try:
            from scipy.optimize._highspy._core import HIGHS_VERSION_MAJOR,HIGHS_VERSION_MINOR,HIGHS_VERSION_PATCH
        except ImportError:
            return f"bundled in SciPy {version('scipy')}"
        return ".".join(map(str,(HIGHS_VERSION_MAJOR,HIGHS_VERSION_MINOR,HIGHS_VERSION_PATCH)))

    def base(self,optimizer,op,pf,sc):
        lp=optimizer.operations.relaxation(op)
        milp=optimizer.solve_operational_milp(op)
        fixed=optimizer.extract_fixed_lp_duals(op,milp.y)
        if lp.objective<milp.objective-TOL or abs(fixed.objective-milp.objective)>TOL:
            raise RuntimeError("LP/MILP/Fixed LP objectives disagree")
        operations_exact=optimizer.operations.enumerate_modes(op)
        exact=optimizer.solve_portfolio_knapsack(pf)
        feasible,examined=optimizer.portfolio.enumerate(pf)
        enumeration=max(feasible,key=lambda p:p.npv)
        greedy,attempts=optimizer.portfolio.greedy(pf)
        control=optimizer.portfolio.metrics(pf,(1,4,5,7))
        if examined!=128 or not optimizer.portfolio.feasible(pf,control) or (control.capex,control.npv,control.score)!=(120,90,320):
            raise RuntimeError("Reference portfolio control failed")
        cbc=CbcCertificate(self.logs)
        references=[
            numerical_row("LP objective",lp.objective,cbc.operations(op,sc.gap_limit,continuous=True),"тыс. руб.","PuLP/CBC",.01),
            numerical_row("MILP objective",milp.objective,cbc.operations(op,sc.gap_limit),"тыс. руб.","PuLP/CBC",.01),
            numerical_row("Fixed LP objective",fixed.objective,cbc.operations(op,sc.gap_limit,continuous=True,fixed_y=milp.y),"тыс. руб.","PuLP/CBC",.01),
            numerical_row("MILP eight modes",milp.objective,operations_exact.objective,"тыс. руб.","8 Fixed LP modes"),
            numerical_row("Knapsack CBC",exact.npv,cbc.portfolio(pf,sc.gap_limit),"млн руб.","PuLP/CBC"),
            numerical_row("Knapsack 128 masks",exact.npv,enumeration.npv,"млн руб.","Combinatorial enumeration"),
        ]
        if any(r["status"]!="PASS" for r in references):
            raise RuntimeError("Independent numerical reconciliation failed")
        cbc_log=(self.logs/"cbc_milp.log").read_text(encoding="utf-8",errors="replace")
        cbc_version=re.search(r"Version:\s*(\S+)",cbc_log)
        return dict(lp=lp,milp=milp,fixed=fixed,exact=exact,enumeration=enumeration,greedy=greedy,control=control,
                    feasible_count=len(feasible),greedy_attempts=attempts,references=references,
                    cbc_version=cbc_version.group(1) if cbc_version else "see CBC solver log")

    def run(self,excel_enabled,editors_enabled):
        self.logs.mkdir(exist_ok=True)
        self.data.mkdir(exist_ok=True)
        lock=self.app/".pipeline.lock"
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:
            return {"status":"FAIL","stages":[dict(stage="0",status="FAIL",artifact="logs",detail="Active pipeline lock")]}
        try:
            os.close(fd)
            working=self.app/f".run-{uuid4().hex}"
            # The output published from this tree must inherit the workspace ACL.
            working.mkdir()
            try:
                return self.execute(working,excel_enabled,editors_enabled)
            finally:
                if working.resolve().parent==self.app.resolve():
                    rmtree(working)
        finally:
            lock.unlink()

    def execute(self,working,excel_enabled,editors_enabled):
        out=working/"candidate"
        out.mkdir()
        tables=out/"tables"; charts=out/"charts"
        tables.mkdir(); charts.mkdir()
        manifest={"started":timestamp(),"status":"FAIL"}
        stage="0"
        h=Harness(self.app,self.logs,out)
        try:
            pdf=PdfExtractor.locate(self.app)
            self.source(pdf,self.data/"source_assignment.pdf")
            lecture=self.source(self.app.parent.parent/"lectuion"/LECTURE_NAME,self.data/"source_lecture9.pdf")
            template=self.source(self.app.parent.parent/"lectuion"/TEMPLATE_NAME,self.data/"report_template.docx")
            manifest.update(self.metadata(pdf,lecture,template))
            h.assumptions.extend([
                dict(id="A01",decision="Квартальная операционная задача и независимый трёхлетний портфель."),
                dict(id="A02",decision="Weighted sum min–max по всему допустимому множеству. Для равных NPV в ε применяется приоритет MCDA."),
                dict(id="A03",decision="Угол дискретного фронта проверяется при масштабах 0,8/1,0/1,25. Минимальное значение 1°."),
            ])
            payload=pdf.read_bytes()
            manifest["sources"]["assignment"]["git_blob_sha1"]=sha1(f"blob {len(payload)}\0".encode()+payload).hexdigest()
            manifest["sources"]["assignment"]["matches_verified_github_blob"]=(
                manifest["sources"]["assignment"]["git_blob_sha1"]=="247f1f451f12eee8cf18f2dda3afbc66401d729d")
            h.emit(stage,"PASS","docs/, run_manifest.json")
            stage="1"
            file=self.data/"inputs.csv"
            raw=PdfExtractor().export(pdf,file)
            op,pf,sc=DataRepository().load(file)
            DataValidationService().validate(op,pf,sc,controls=True)
            manifest["sources"]["inputs_csv"]={"path":"data/inputs.csv","sha256":sha(file)}
            h.emit(stage,"PASS","data/inputs.csv","3 продукта, 3 агрегата, 2 материала, 7 проектов")
            stage="2"
            optimizer=ProductionAndPortfolioOptimizer(sc.gap_limit)
            h.emit(stage,"PASS","src/","Интерфейс → контроллер → сервисы")
            stage="3"
            base=self.base(optimizer,op,pf,sc)
            manifest["solver"]["cbc_version"]=base["cbc_version"]
            manifest["solver"]["mip_gap_limit"]=sc.gap_limit
            ResultTables(tables).base(op,pf,base)
            h.emit(stage,"PASS","output/tables/operations.csv",f'MILP gap={base["milp"].gap:g}')
            stage="4"
            excel=WorkbookService()
            book=out/"Ground_Truth.xlsx"
            checks=excel.build(book,op,pf,sc,base,raw)
            h.reconciliation,base_excel=excel.verify(book,checks,self.logs,base["references"],base,excel_enabled,"excel_base.log")
            if base_excel["status"]=="FAIL":
                raise RuntimeError("Excel base numerical reconciliation failed")
            manifest["excel_base"]=base_excel
            h.emit("4A","PASS" if base_excel["status"]=="PASS" else "PASS_WITH_LIMITATIONS",
                   "output/tables/portfolio_comparison.csv, logs/excel_base.log",
                   f'Knapsack, 128 вариантов, CBC, Excel: {base_excel["status"]}')
            stage="5"
            tests=h.run_tests()
            h.emit(stage,"PASS","logs/tests.log",f"{tests} тестов PASS")
            stage="6"
            pa=ParetoAnalysis(optimizer.portfolio).run(pf,sc.epsilon_step,sc.mrt_limit)
            h.emit(stage,"PASS","output/tables/pareto_nondominated.csv",f'{len(pa["frontier"])} точки фронта')
            stage="7"
            sa=ScenarioAnalysis(optimizer)
            edges=sa.edges(op,pf,sc,base["milp"])
            stress=sa.stress(op,pf,sc,base["milp"],base["exact"])
            ResultTables(tables).analysis(pa,stress,base,edges,sc)
            h.emit(stage,"PASS","output/tables/stress_portfolio.csv, mrt.csv, knee.csv")
            stage="4B"
            checks=excel.build(book,op,pf,sc,base,raw,pa,stress)
            recon,excel_status=excel.verify(book,checks,self.logs,base["references"],base,excel_enabled)
            h.reconciliation=recon
            manifest["excel"]=excel_status
            write_csv(out/"reconciliation.csv",recon)
            if excel_status["status"]=="FAIL":
                raise RuntimeError("Excel numerical reconciliation failed")
            if excel_status["status"]!="PASS":
                h.errors.append(dict(code="EXCEL_NOT_VERIFIED",stage="4B",expected="Excel Solver 0 and recalculation",
                                     observed=(self.logs/"excel.log").read_text(encoding="utf-8",errors="replace"),
                                     cause="COM or Solver unavailable, see logs/excel.log"))
            h.emit(stage,"PASS" if excel_status["status"]=="PASS" else "NOT_VERIFIED",
                   "output/Ground_Truth.xlsx, output/reconciliation.csv",excel_status["status"])
            stage="8"
            chart_catalog=ChartService(tables,charts,self.app/"docs/visual_review.json").run()
            chart_review=all(row["visual"]=="PASS" for row in chart_catalog)
            h.emit(stage,"PASS" if chart_review else "NOT_VERIFIED","output/tables/chart_catalog.csv",
                   f'{len(chart_catalog)} PNG, ' + ("просмотр подтверждён" if chart_review else "VISUAL_NOT_VERIFIED"))
            stage="9"
            brief=prepare_brief(op,pf,sc,base,pa,stress,edges,recon,excel_status,tests)
            ReportService(out,template).run(brief)
            SlideDeck(out).run(brief)
            editor=render_office(out,self.logs,self.app/"docs/editor_review.json",editors_enabled)
            manifest["editors"]=editor
            editor_review=bool(editor.get("rendered")) and all(d["visual"]=="PASS" for d in editor["rendered"].values())
            h.emit(stage,"PASS" if editor_review else "PASS_WITH_LIMITATIONS","output/*.docx, output/*.pptx",
                   editor["status"] + ("" if editor_review else " / VISUAL_NOT_VERIFIED"))
            stage="10"
            h.emit(stage,"PASS","output/"+ARCHIVE,"CRC и SHA256 вложений")
            h.export()
            audit=audit_reports(out,excel_status.get("sensitivity_sheets",[]))
            json_to(out/"document_audit.json",audit)
            manifest["status"]=("PASS" if excel_status["status"]=="PASS" and chart_review and editor_review else "PASS_WITH_LIMITATIONS")
            manifest["stages"]=h.events
            manifest["finished"]=timestamp()
            manifest["summary"]=dict(profit_thousand=base["milp"].objective,lp_profit_thousand=base["lp"].objective,
                production_tons=list(base["milp"].x),fixed_lp_shadow=list(base["fixed"].shadow),
                base_npv=base["exact"].npv,base_ids=ids(base["exact"]),greedy_npv=base["greedy"].npv,
                finance_npv=stress["finance"].npv,green_npv=stress["green"].npv,
                carbon_profit_loss_thousand=stress["carbon_profit_loss"],tests=tests,
                excel_checks=brief["excel_checks"],numeric_checks=brief["numeric_checks"])
            inner=out/"run_manifest.json"
            json_to(inner,manifest)
            manifest["archive"]=package(self.app,out,self.logs,inner)
            previous=working/"previous_output"
            target=self.app/"output"
            if target.exists():
                target.rename(previous)
            try:
                out.rename(target)
            except OSError:
                if previous.exists():
                    previous.rename(target)
                raise
            json_to(self.app/"run_manifest.json",manifest)
        except Exception as error:
            h.error(stage,error)
            h.emit(stage,"FAIL","logs/execution.log",str(error))
            (self.logs/"failure_traceback.log").write_text(traceback.format_exc(),encoding="utf-8")
            # Keep the last successful directory separate from the failed attempt.
            h.output=self.logs
            h.export()
            manifest.update(status="FAIL",finished=timestamp(),stages=h.events,active_failure=str(error))
            json_to(self.app/"run_manifest.json",manifest)
        return manifest
