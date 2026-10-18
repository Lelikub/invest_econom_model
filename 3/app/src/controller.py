"""One-command orchestration, without embedded financial formulas."""
from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import pymupdf
import pandas as pd
from .io_utils import sha256,write_csv,write_json
from .repositories import DataRepository
from .models import PipelineConfig
from .services.extraction import PdfExtractionService
from .services.validation import DataValidationService
from .services.logging_service import LoggingService
from .services.metrics import MetricService
from .services.market import MarketDataService
from .services.scenarios import ScenarioService
from .services.source_issues import SourceIssueService
from .services.testing import TestService
from .reporting.excel import ExcelGroundTruthWriter,ExcelService,ComparisonService
from .reporting.charts import ChartWriter
from .reporting.harness import HarnessLogWriter
from .reporting.report import WordReportWriter,ArtifactValidationService,REPORT_NAME,ARCHIVE_NAME


METRIC_UNITS={key:('million USD/year' if key=='ebitda' else 'million USD' if key in ('equity','debt') else
    'fraction/year' if key in ('rf','erp','crp','ke','kd','kd_after_tax','wacc','credit_spread','pi_exp') else
    'fraction' if key in ('t_eff','we','wd','delta_total') else 'ratio') for key in (
    't_eff','de_peer','beta_u','de','beta_l','rf','erp','crp','we','wd','ke','kd','kd_after_tax','wacc','dscr',
    'equity','debt','ebitda','credit_spread','delta_total','pi_exp','beta_multiplier')}


class PipelineController:
    def __init__(self,config: PipelineConfig,logger=None):
        self.config=config
        self.log=logger or LoggingService(config.app_dir)

    def run(self):
        cfg=self.config; app=cfg.app_dir.resolve(); output=cfg.output.resolve()
        start=time.monotonic(); step='inventory'
        manifest=dict(run_id=self.log.run_id,status='RUNNING',started_at=datetime.now(ZoneInfo('Europe/Moscow')).isoformat(),stages={})
        try:
            if not output.is_relative_to(app): raise ValueError('Output must stay inside 3/app')
            output.mkdir(parents=True,exist_ok=True)
            tables=output/'tables'; tables.mkdir(parents=True,exist_ok=True)
            data=app/'data'; data.mkdir(parents=True,exist_ok=True)
            docs=app/'docs'; docs.mkdir(parents=True,exist_ok=True)
            # Save previous primary artifacts before starting, so a failed run
            # cannot expose an old report as a new successful result.
            prior=app/'logs/prior_outputs'/self.log.run_id
            for name in ('Ground_Truth.xlsx','HARNESS_LOG.xlsx',REPORT_NAME,ARCHIVE_NAME):
                file=output/name
                if file.exists():
                    prior.mkdir(parents=True,exist_ok=True)
                    shutil.move(str(file),str(prior/name))
            sources={}
            for name,path in [('assignment',cfg.pdf),('prices',cfg.prices),('lecture5',cfg.lecture)]:
                if not path.is_file(): raise FileNotFoundError(path)
                sources[name]=dict(path=os.path.relpath(path,app),sha256=sha256(path),bytes=path.stat().st_size)
                destination=data/({'assignment':'source_assignment.pdf','prices':'hxl_gspc_adj_close_5y.csv','lecture5':'source_lecture5.pdf'}[name])
                if path.resolve()!=destination.resolve(): shutil.copy2(path,destination)
                if sha256(destination)!=sources[name]['sha256']: raise ValueError('Input copy mismatch')
                sources[name]['archive_copy']=str(destination.relative_to(app))
            def git(*args):
                proc=subprocess.run(['git',*args],cwd=app,capture_output=True,text=True,encoding='utf-8',errors='replace')
                return proc.stdout.strip() if proc.returncode==0 else 'UNKNOWN'
            versions={package:importlib.metadata.version(package) for package in (
                'pymupdf','numpy','pandas','scipy','openpyxl','python-docx','matplotlib','pytest','pywin32')}
            manifest.update(sources=sources,commit=git('rev-parse','HEAD'),branch=git('branch','--show-current'),
                environment=dict(python=sys.version,platform=platform.platform(),dependencies=versions),
                architecture_deviations='Layered calculators, per-parameter PDF provenance, chart and calendar audits; independent of apps 1/2')
            self.log.log(step,f'commit={manifest["commit"]}; sources={list(sources)}')
            development=app/'docs/development_observations.json'
            if development.exists():
                for event in json.loads(development.read_text(encoding='utf-8')):
                    self.log.issue(**event)
            step='pdf_extraction'
            parameters=PdfExtractionService().extract(cfg.pdf,data)
            inputs=DataRepository.load(data); p,m,s=inputs
            audit=DataValidationService.validate_inputs(*inputs)
            for row in audit: self.log.log('data_validation',str(row))
            lecture_text=''
            with pymupdf.open(cfg.lecture) as lecture:
                lecture_text='\n'.join(f'=== PAGE {i+1} ===\n{page.get_text()}' for i,page in enumerate(lecture))
            (docs/'lecture5_text.txt').write_text(lecture_text,encoding='utf-8')
            issues=SourceIssueService().collect(*inputs,parameters,(data/'assignment_text.txt').read_text(encoding='utf-8'),
                lecture_text,docs,self.log)
            manifest['stages']['PDF_CSV']=dict(status='PASS',parameters=len(parameters),copied_prices_hash_match=True)
            step='base'
            base=MetricService().base(p,m)
            write_csv(tables/'base_metrics.csv',[dict(metric_id=k,value=v,unit=METRIC_UNITS[k],scenario='base') for k,v in base.metrics.items()])
            self.log.log(step,f'WACC={base.metrics["wacc"]:.12f}')
            step='market_ols'
            series,monthly,returns,regression,market_audit=MarketDataService().process(data/'hxl_gspc_adj_close_5y.csv',tables)
            audit.extend(market_audit)
            for row in market_audit: self.log.log('data_validation',str(row))
            for row in audit:
                if row['status']!='PASS':
                    self.log.issue('audit_'+row['check'],'data','Проверить адекватность данных','DataValidationService',
                        row['details'],row['status'],'Сохранено в data_audit.csv; данные не заменяются',row['status'],'data anomaly' if row['status']=='WARNING' else 'verification limit')
            write_csv(tables/'data_audit.csv',audit)
            write_csv(tables/'beta_comparison.csv',MetricService.beta_comparison(regression,m))
            manifest['stages']['OLS']=dict(status='PASS',daily_rows=len(series.frame),monthly_prices=len(monthly),monthly_returns=len(returns),**asdict(regression))
            step='stress'
            stress,wf,literal,diagnostics,discount=ScenarioService().run(p,m,s,base,tables)
            write_csv(tables/'stress_metrics.csv',[dict(metric_id=k,value=v,unit=METRIC_UNITS[k],scenario='stress') for k,v in stress.metrics.items()])
            write_csv(tables/'comparison.csv',MetricService.metric_comparison(base,stress,METRIC_UNITS))
            decomposition=MetricService.decomposition(base,stress)
            write_csv(tables/'wacc_decomposition.csv',decomposition)
            # Explicit sensitivity to the otherwise ambiguous Taiwan CRP mapping.
            write_csv(tables/'taiwan_mapping_sensitivity.csv',MetricService.taiwan_sensitivity(stress,s))
            manifest['stages']['Stress']=dict(status='PASS',metrics=len(stress.metrics),wacc=stress.metrics['wacc'])
            manifest['stages']['Waterfall']=dict(status='ILLUSTRATIVE',known_ebitda=stress.metrics['ebitda'],
                contractual_debt=p.debt_service,dividend_lockup=wf.dividend_lockup,full_cash_waterfall='BLOCKED: missing cash taxes/NWC/DSRA inputs')
            step='tests'
            tests=TestService().run(app,tables,self.log)
            manifest['stages']['Tests']=dict(status='PASS',passed=len(tests),total=len(tests))
            step='excel'
            excel=output/'Ground_Truth.xlsx'
            refs=ExcelGroundTruthWriter().write(excel,p,m,s,base,stress,returns,audit,tests,(wf,literal),parameters)
            excel_status,excel_detail=ExcelService(cfg.excel_timeout).recalculate(excel)
            self.log.log(step,excel_status+' '+excel_detail)
            if excel_status!='PASS':
                self.log.issue('excel_engine','excel','Пересчитать независимую книгу','ExcelService.recalculate',excel_detail,
                    'Движок недоступен/ошибка исполнения','Формулы сохранены, совпадение не подтверждено','NOT_VERIFIED','verification limit')
            lookup_extra=MetricService.verification_lookup(discount,decomposition)
            reconciliation=ComparisonService.reconcile(excel,refs,base,stress,excel_status=='PASS',regression,(wf,literal),lookup_extra)
            for row in reconciliation:
                row['unit']=METRIC_UNITS.get(row['metric_id'],
                    'PV USD / future USD' if row['scenario'].startswith('discount') else
                    'fraction/year' if row['scenario']=='decomposition' else
                    'million USD/year' if row['scenario'] in ('waterfall','literal') and row['metric_id']!='dividend_lockup' else 'ratio/boolean')
            write_csv(tables/'reconciliation.csv',reconciliation)
            if any(r['verification_status']=='FAIL' for r in reconciliation): raise ValueError('Python/Excel mismatch')
            manifest['stages']['Excel']=dict(status=excel_status,metrics=len(reconciliation),
                passed=sum(r['verification_status']=='PASS' for r in reconciliation),engine=excel_detail)
            step='charts'
            charts=ChartWriter(output,self.log).build(series.frame,returns,regression,base,stress,p,s,wf,pd.DataFrame(discount),pd.DataFrame(diagnostics))
            manifest['stages']['Charts']=dict(status='PASS',count=len(charts),visual_pass=sum(r['visual_status']=='PASS' for r in charts))
            if any(r['visual_status']!='PASS' for r in charts):
                self.log.issue('visual_review','charts','Просмотреть финальные PNG','ChartWriter',
                    'PNG созданы; hash-bound запись отдельного просмотра отсутствует для части графиков',
                    'Автоматический аудит не равен визуальному просмотру','Графики доступны для просмотра; отдельный статус NOT_VERIFIED',
                    'NOT_VERIFIED','verification limit')
            else:
                self.log.issue('visual_review','charts','Просмотреть финальные PNG','docs/visual_review.json',
                    'Имеются записи просмотра для текущих SHA256 всех PNG','Независимый от автоаудита визуальный просмотр',
                    'Сверены SHA256 PNG с записью просмотра',f'PASS {len(charts)}/{len(charts)}','verification limit')
            status='COMPLETED_WITH_LIMITATIONS' if excel_status=='PASS' and all(c['visual_status']=='PASS' for c in charts) else 'NOT_VERIFIED'
            manifest['status']=status
            step='report'
            HarnessLogWriter.write(output/'HARNESS_LOG.xlsx',self.log.history())
            context=dict(status=status,manifest=manifest,inputs=inputs,parameters=parameters,audit=audit,
                base=base,stress=stress,regression=regression,tests=tests,waterfall=wf,literal=literal,
                charts=charts,prices=series.frame,monthly=monthly,decomposition=decomposition,discount=discount,
                units=METRIC_UNITS,reconciliation=reconciliation,events=self.log.history(),issues=issues,
                excel_detail=excel_detail,output=output)
            report=WordReportWriter().write(output/REPORT_NAME,context)
            manifest['stages']['Word_Render']=ArtifactValidationService.render_review_pdf(output/REPORT_NAME)
            self.log.log('word_render',str(manifest['stages']['Word_Render']))
            manifest['stages']['Artifacts']=ArtifactValidationService.verify(output,charts)
            manifest['report']=report
            manifest['duration_seconds']=round(time.monotonic()-start,3)
            manifest['finished_at']=datetime.now(ZoneInfo('Europe/Moscow')).isoformat()
            write_json(app/'run_manifest.json',manifest)
            write_json(output/'run_manifest.json',manifest)
            archive=ArtifactValidationService.archive(app,output)
            manifest['archive']=archive
            write_json(app/'run_manifest.json',manifest); write_json(output/'run_manifest.json',manifest)
            # Repackage once with the final manifest; the archive excludes itself.
            ArtifactValidationService.archive(app,output)
            self.log.log('complete',f'{status}; tests={len(tests)}; Excel={excel_status}; charts={len(charts)}; archive CRC PASS')
            return manifest
        except Exception as exc:
            self.log.exception(step,exc)
            manifest.update(status='FAILED',failed_step=step,error=str(exc),duration_seconds=round(time.monotonic()-start,3))
            # Even malformed input gets a usable diagnosis and observed Harness.
            if not output.is_relative_to(app): output=app/'output'
            output.mkdir(parents=True,exist_ok=True)
            HarnessLogWriter.write(output/'HARNESS_LOG.xlsx',self.log.history())
            write_json(app/'run_manifest.json',manifest); write_json(output/'run_manifest.json',manifest)
            return manifest
