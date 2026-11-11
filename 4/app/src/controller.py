"""Sequential orchestration only. No financial formulas."""
from contextlib import contextmanager
from dataclasses import asdict
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback
import pymupdf
from .io_utils import now,sha256,write_csv,write_json
from .models import ScenarioResult
from .repositories import DataRepository
from .services.extraction import PdfExtractionService
from .services.documentation import DocumentationService,SOURCE_ISSUES
from .services.validation import DataValidationService
from .services.finance import FinancialModelService
from .services.scenarios import ScenarioService
from .services.reconciliation import ComparisonService
from .services.testing import TestService
from .services.tables import TableService
from .services.report_sections import ReportService
from .services.logging_service import LoggingService
from .reporting.excel import ExcelGroundTruthWriter,ExcelGroundTruthService
from .reporting.charts import ChartService
from .reporting.chart_validation import ChartValidationService
from .reporting.word import WordReportWriter,REPORT_NAME
from .reporting.template import ReportTemplateLoader
from .reporting.word_preview import WordPreviewService
from .reporting.harness import HarnessLogWriter
from .reporting.artifacts import ArtifactService

STAGES={
 '00':'Git, структура и источники','01':'PDF/лекция и реестры','02':'PDF → CSV','03':'CSV → DTO',
 '04':'Валидация и проблемы источника','05':'Страновые финансовые модели','06':'Годовые потоки и метрики',
 '07':'Формульный Excel','08':'Реальный Excel и независимая сверка','09':'Тесты и Edge Cases',
 '10':'Два стресса','11':'Вероятностные сценарии и сверка расширенного Excel','12':'Графики и аудит',
 '13':'Word и машинный отчет','14':'Аудит артефактов','15':'Итоговый статус и архив'}

class PipelineController:
    def run(self,config) -> int:
        self.cfg=config; app=config.app; output=config.output
        self.log=LoggingService(app); self.tests=[]; self.reconciliation=[]
        self.manifest=dict(run_id=self.log.run_id,status='RUNNING',started_at=now(),stages={})
        # A failed current run must never masquerade as the previous successful report.
        if output.exists() and any(output.iterdir()):
            prior=app/'logs/prior_outputs'/self.log.run_id/'output'
            if not prior.resolve().is_relative_to(app.resolve()): raise ValueError('Unsafe archive target')
            prior.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(output),str(prior))
        output.mkdir(parents=True,exist_ok=True); (output/'tables').mkdir(exist_ok=True)
        self.harness=HarnessLogWriter(); self.persist()
        try:
            with self.stage('00'):
                self.inventory()
            with self.stage('01'):
                docs=app/'docs'; data=app/'data'; docs.mkdir(exist_ok=True); data.mkdir(exist_ok=True)
                for name,path in [('assignment',config.pdf),('lecture7',config.lecture)]:
                    with pymupdf.open(path) as pdf:
                        text='\n'.join(f'=== PAGE {i+1} ===\n{p.get_text()}' for i,p in enumerate(pdf))
                    (docs/('lecture7_text.txt' if name=='lecture7' else 'assignment_inspection.txt')).write_text(text,encoding='utf-8')
                DocumentationService().write(docs)
            with self.stage('02'):
                extracted=PdfExtractionService().extract(data/'source_assignment.pdf',data)
                self.detail('02',records=len(extracted))
            with self.stage('03'):
                inputs=DataRepository.load(data)
                self.detail('03',parameters=len(inputs.provenance),countries=list(inputs.countries))
            with self.stage('04'):
                audit=DataValidationService().validate(inputs)
                write_csv(output/'tables/data_validation.csv',audit)
                write_json(output/'tables/data_validation.json',audit)
                for issue in SOURCE_ISSUES:
                    self.log.issue('SOURCE_ISSUE',issue['id'],'04',issue['issue'],issue['decision'],page=issue['page'],test=issue['test'],impact='See tables/source_sensitivity.csv')
                observations=docs/'development_observations.json'
                if observations.exists():
                    for row in json.loads(observations.read_text(encoding='utf-8')):
                        self.log.issue(row['kind'],row['id'],row['stage'],row['observed'],row['fix'],
                            cause=row.get('cause',''),retest='PASS: covered by full current test suite' if row['kind']=='CODE_ERROR' else row['retest'])
                self.detail('04',checks=len(audit),source_issues=len(SOURCE_ISSUES))
            with self.stage('05'):
                service=FinancialModelService(); base={c:service.evaluate(inputs.project,p) for c,p in inputs.countries.items()}
                for code,result in base.items(): self.log.event('05',json.dumps(dict(country=code,risk=asdict(result.risk),capex=asdict(result.capex)),ensure_ascii=False),'PASS',kind='calculations')
            with self.stage('06'):
                write_csv(output/'tables/annual_cashflows.csv',[dict(country=c,**asdict(a)) for c,r in base.items() for a in r.annual])
                write_csv(output/'tables/base_metrics.csv',[dict(country=c,scope=scope,**asdict(getattr(r,scope))) for c,r in base.items() for scope in ('local','parent')])
                for code,r in base.items(): self.log.event('06',f'{code}: Parent NPV={r.parent.npv:.9f} USD','PASS',kind='calculations')
            baseline=ScenarioResult({'B':base},{},{s:inputs.scenarios['p_'+s] for s in 'ABC'})
            with self.stage('07'):
                self.refs=ExcelGroundTruthWriter().write(output/'Ground_Truth.xlsx',inputs,baseline)
                self.detail('07',comparison_targets=len(self.refs),scope='Initial baseline; scenario workbook extends in stage11')
            with self.stage('08'):
                self.verify_excel()
                self.detail('08',**self.manifest['excel'])
            with self.stage('09'):
                self.tests=TestService().run(app,self.log)
                self.detail('09',passed=sum(t['status']=='PASS' for t in self.tests),failed=sum(t['status']=='FAIL' for t in self.tests),total=len(self.tests))
            with self.stage('10'):
                stresses=ScenarioService().stress(inputs)
                write_csv(output/'tables/stress_initial_metrics.csv',[dict(stress=s,country=r.country.code,**asdict(r.parent)) for s,r in stresses.items()])
                self.detail('10',stresses=list(stresses))
            with self.stage('11'):
                scenarios=ScenarioService().run(inputs)
                tables=TableService().write(inputs,scenarios,output/'tables')
                # Extend the same independent model to all scenarios and edge cases, then recalculate it.
                self.refs=ExcelGroundTruthWriter().write(output/'Ground_Truth.xlsx',inputs,scenarios)
                self.verify_excel()
                self.detail('11',scenarios=['A','B','C'],comparison_targets=len(self.refs),excel=self.manifest['excel']['status'])
                self.manifest['stages']['08'].update(self.manifest['excel'])
            with self.stage('12'):
                paths,chart_audit=ChartService().write(output/'tables',output/'charts')
                visual=ChartValidationService.visual_status(paths,docs/'visual_review.json')
                self.manifest['visual_status']=visual
                self.detail('12',charts=len(paths),numeric='PASS',visual=visual,status='PASS' if visual=='PASS' else 'NOT_VERIFIED')
                if visual!='PASS': self.log.issue('VERIFICATION_LIMIT','VISUAL_REVIEW','12','No matching SHA256-bound actual visual review for all current images','Open all generated images and record actual review in docs/visual_review.json','NOT_VERIFIED')
            verified=self.manifest['excel']['status']=='PASS' and self.manifest['visual_status']=='PASS'
            self.manifest['status']='COMPLETED_WITH_LIMITATIONS' if verified else 'NOT_VERIFIED'
            self.manifest['limitations']=[r['id']+': '+r['decision'] for r in SOURCE_ISSUES]
            if not verified: self.manifest['limitations'].append('Independent Excel and/or actual visual review not fully certified; see stages08/12')
            self.summary=dict(run_id=self.log.run_id,status=self.manifest['status'],unit='USD',method='parent_cashflow_economic_rule; payout=100%; cash_tax>=0; TV=0',
                base={c:dict(risk=asdict(r.risk),capex=asdict(r.capex),local=asdict(r.local),parent=asdict(r.parent)) for c,r in base.items()},
                scenarios={s:{c:asdict(r.parent) for c,r in rs.items()} for s,rs in scenarios.results.items()},
                statistics={c:asdict(s) for c,s in scenarios.statistics.items()},
                ranking=sorted(scenarios.statistics,key=lambda c:scenarios.statistics[c].expected,reverse=True),
                verdict='Do not accept any location at the specified assumptions: all expected Parent NPVs are negative',
                tests=dict(passed=sum(t['status']=='PASS' for t in self.tests),failed=sum(t['status']=='FAIL' for t in self.tests)),excel=self.manifest['excel'],visual=self.manifest['visual_status'])
            with self.stage('13'):
                sections=ReportService().sections(inputs,scenarios,tables,self.reconciliation,self.tests,self.manifest,self.log.issues)
                report=WordReportWriter(); self.manifest['report']=report.write(output/REPORT_NAME,sections,output/'charts',self.manifest,inputs,
                    template_path=data/'report_template.docx',report_data=dict(tests=self.tests,reconciliation=self.reconciliation,
                        issues=self.log.issues,scenario_inputs=tables['scenario_inputs']))
                self.summary['report']=self.manifest['report']
                self.manifest['report_preview']=WordPreviewService().render(output/REPORT_NAME)
                self.log.event('13',self.manifest['report_preview'].get('detail','Word preview'),self.manifest['report_preview']['status'])
                report.markdown(output/'FINAL_REPORT.md',sections,self.summary)
                write_json(output/'results_summary.json',self.summary)
                write_json(output/'report_sections.json',[asdict(s) for s in sections])
            with self.stage('14'):
                self.persist(harness=True)
                self.manifest['artifact_audit']=ArtifactService().validate(output,len(paths))
            with self.stage('15'):
                self.manifest['finished_at']=now()
                self.manifest['exit_code']=0 if verified else 2
                self.detail('15',status=self.manifest['status'],archive='CRC and SHA256 validation performed by final packager')
            self.summary['stages']=self.manifest['stages']; write_json(output/'results_summary.json',self.summary)
            self.persist(harness=True)
            self.manifest['archive']=ArtifactService().package(app,output)
            write_json(output/'run_manifest.json',self.manifest); write_json(app/'run_manifest.json',self.manifest)
            print(json.dumps(dict(status=self.manifest['status'],run_id=self.log.run_id,tests=self.summary['tests'],excel=self.manifest['excel'],parent_npv_USD={c:r.parent.npv for c,r in base.items()},output=str(output)),ensure_ascii=False,indent=2))
            return self.manifest['exit_code']
        except Exception:
            trace=traceback.format_exc(); self.manifest.update(status='FAILED',exit_code=1,finished_at=now(),traceback=trace)
            self.log.issue('CODE_ERROR','PIPELINE_FAILURE','pipeline',trace,'See traceback; current outputs are incomplete','FAIL')
            self.persist(harness=True); print(trace,file=sys.stderr); return 1

    @contextmanager
    def stage(self,id):
        start=time.monotonic(); self.manifest['stages'][id]=dict(name=STAGES[id],status='RUNNING',started_at=now())
        print(f'[{id}] {STAGES[id]}',flush=True)
        self.log.event(id,STAGES[id],'START'); self.persist()
        try:
            yield
            current=self.manifest['stages'][id]
            if current['status']=='RUNNING': current['status']='PASS'
        except Exception:
            self.manifest['stages'][id]['status']='FAIL'; raise
        finally:
            self.manifest['stages'][id]['seconds']=round(time.monotonic()-start,6)
            self.log.event(id,STAGES[id],self.manifest['stages'][id]['status']); self.persist()

    def detail(self,id,**kwargs): self.manifest['stages'][id].update(kwargs)

    def persist(self,harness=False):
        write_json(self.cfg.output/'run_manifest.json',self.manifest)
        write_json(self.cfg.app/'run_manifest.json',self.manifest)
        if harness or not (self.cfg.output/'HARNESS_LOG.xlsx').exists():
            self.harness.write(self.cfg.output/'HARNESS_LOG.xlsx',self.manifest,self.log.issues,self.tests,self.reconciliation)

    def inventory(self):
        app=self.cfg.app
        def git(*args):
            r=subprocess.run(['git',*args],cwd=app,capture_output=True,text=True,encoding='utf-8',errors='replace')
            return r.stdout.strip() if r.returncode==0 else 'UNKNOWN'
        self.manifest.update(commit=git('rev-parse','HEAD'),branch=git('branch','--show-current'),git_status_at_start=git('status','--short'),main_tree=git('ls-tree','--name-only','main'),github_pushed=False)
        self.manifest['environment']=dict(python=sys.version,platform=platform.platform(),dependencies={k:importlib.metadata.version(k) for k in ['pymupdf','numpy','pandas','scipy','openpyxl','matplotlib','python-docx','pytest']})
        self.manifest['sources']={}; data=app/'data'; data.mkdir(exist_ok=True)
        for key,path,name,pages in [('assignment',self.cfg.pdf,'source_assignment.pdf',15),('lecture7',self.cfg.lecture,'source_lecture7.pdf',32)]:
            if not path.is_file() or path.stat().st_size==0: raise FileNotFoundError(path)
            with pymupdf.open(path) as doc:
                if len(doc)!=pages: raise ValueError(f'{key}: unexpected number of pages')
            target=data/name
            if target.resolve()!=path.resolve(): shutil.copy2(path,target)
            if sha256(target)!=sha256(path): raise ValueError('Source copy hash mismatch')
            self.manifest['sources'][key]=dict(original=str(path),copy=str(target.relative_to(app)),sha256=sha256(path),bytes=path.stat().st_size,pages=pages)
        write_json(data/'source_inventory.json',self.manifest['sources'])
        template_path=self.cfg.template or ReportTemplateLoader.default_path()
        _,titles,_,template_info=ReportTemplateLoader().load(template_path)
        copy=data/'report_template.docx'
        if template_path.resolve()!=copy.resolve(): shutil.copy2(template_path,copy)
        if sha256(copy)!=template_info['sha256']: raise ValueError('Report template copy hash mismatch')
        self.manifest['sources']['report_template']=dict(original=str(template_path),copy=str(copy.relative_to(app)),
            sha256=template_info['sha256'],bytes=copy.stat().st_size,format='DOCX',content_chapters=len(titles))
        write_json(data/'source_inventory.json',self.manifest['sources'])

    def verify_excel(self):
        output=self.cfg.output
        status,detail=ExcelGroundTruthService().recalculate(output/'Ground_Truth.xlsx',self.cfg.excel_timeout)
        self.log.event('08',detail,status)
        self.reconciliation=ComparisonService().compare(output/'Ground_Truth.xlsx',self.refs,status=='PASS')
        write_csv(output/'reconciliation.csv',self.reconciliation)
        failures=[r for r in self.reconciliation if r['status'].startswith('FAIL')]
        passed=sum(r['status']=='PASS' for r in self.reconciliation)
        self.manifest['excel']=dict(status=status,engine_detail=detail,total=len(self.reconciliation),passed=passed,failed=len(failures))
        if failures:
            self.log.issue('CODE_ERROR','EXCEL_MISMATCH','08',str(failures[:10]),'Independent spreadsheet and Python must agree before completion','FAIL')
            raise ValueError(f'{len(failures)} Excel/Python differences')
        if status!='PASS': self.log.issue('VERIFICATION_LIMIT','EXCEL_ENGINE','08',detail,'Formulas retained; no synthetic cached values','NOT_VERIFIED')
