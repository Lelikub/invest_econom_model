from pathlib import Path
from dataclasses import replace
import pytest
from openpyxl import load_workbook

def test_excel_contains_formulas_for_scenarios_and_every_year(inputs,tmp_path):
    from src.reporting.excel import ExcelGroundTruthWriter
    from src.services.scenarios import ScenarioService
    path=tmp_path/'ground.xlsx'
    refs=ExcelGroundTruthWriter().write(path,inputs,ScenarioService().run(inputs))
    wb=load_workbook(path,data_only=False)
    assert {'Sources','Inputs','Risk_Rates','CAPEX_Subsidies','Supply_Chains','Time_Schedule','Taxation','Cashflows_DEU','Cashflows_SRB','Cashflows_VNM','Financial_Metrics','Comparison','Assumptions','Source_Issues'}<=set(wb.sheetnames)
    assert len(refs)>9000
    for ref in refs:
        assert wb[ref['sheet']][ref['cell']].data_type=='f',ref
    assert any(r['scenario']=='ZERO' for r in refs)

def test_empty_cache_never_matches(inputs,tmp_path):
    from src.reporting.excel import ExcelGroundTruthWriter
    from src.services.scenarios import ScenarioService
    from src.services.reconciliation import ComparisonService
    path=tmp_path/'uncached.xlsx'
    refs=ExcelGroundTruthWriter().write(path,inputs,ScenarioService().run(inputs))
    rows=ComparisonService().compare(path,refs,False)
    assert rows and {r['status'] for r in rows}=={'NOT_VERIFIED'}

def test_invalid_pdf(tmp_path):
    from src.services.extraction import PdfExtractionService
    bad=tmp_path/'bad.pdf'; bad.write_bytes(b'not a PDF')
    with pytest.raises(Exception): PdfExtractionService().extract(bad,tmp_path/'data')

@pytest.mark.parametrize('fault',['unit','missing','duplicate'])
def test_bad_csv(inputs,tmp_path,fault):
    from src.repositories import DataRepository
    from src.io_utils import write_csv
    from src.services.extraction import PdfExtractionService
    from conftest import APP
    pdf=APP/'data/source_assignment.pdf'
    if not pdf.exists(): pdf=next((APP.parent/'data').glob('*.pdf'))
    PdfExtractionService().extract(pdf,tmp_path)
    from src.io_utils import read_csv
    path=tmp_path/'project_constants.csv'; rows=read_csv(path)
    if fault=='unit':
        next(r for r in rows if r['parameter_id']=='wacc')['unit']='percent'
    elif fault=='missing': rows=[r for r in rows if r['parameter_id']!='wacc']
    else: rows.append(rows[0].copy())
    write_csv(path,rows)
    with pytest.raises(ValueError): DataRepository.load(tmp_path)

def test_chart_axis_validation():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.reporting.chart_validation import ChartValidationService
    fig,ax=plt.subplots(); ax.plot([0,13],[0,10]); ax.set_xlim(0,10)
    with pytest.raises(ValueError): ChartValidationService.validate_axis(ax,[0,13],[0,10])
    plt.close(fig)

def test_visual_hash_invalidation(tmp_path):
    from src.reporting.chart_validation import ChartValidationService
    from src.io_utils import sha256,write_json
    p=tmp_path/'a.png'; p.write_bytes(b'old')
    review=tmp_path/'review.json'
    write_json(review,[dict(filename='a.png',SHA256=sha256(p),status='PASS',reviewer='test')])
    assert ChartValidationService.visual_status([p],review)=='PASS'
    p.write_bytes(b'new')
    assert ChartValidationService.visual_status([p],review)=='VISUAL_NOT_VERIFIED'

def test_report_embeds_sections_in_order(tmp_path):
    from src.models import ReportSectionDTO
    from src.reporting.word import WordReportWriter
    from docx import Document
    section=ReportSectionDTO('T01','Контроль','table1',None,('Страна','NPV, USD'),(('DEU',-10.),),'Анализ: NPV отрицателен.')
    p=tmp_path/'report.docx'; WordReportWriter().write(p,[section],tmp_path,{'status':'NOT_VERIFIED'})
    d=Document(p); assert len(d.tables)>=1
    assert any('NPV отрицателен' in p.text for p in d.paragraphs)

def test_output_cannot_escape_app(tmp_path):
    from src.interface import ApplicationInterface
    assert ApplicationInterface().run(['--output',str(tmp_path)])==1

def test_harness_csv_preserves_heterogeneous_diagnostics(tmp_path):
    from src.io_utils import write_csv,read_csv
    p=tmp_path/'issues.csv'
    write_csv(p,[dict(id='SOURCE',page='13'),dict(id='CODE',retest='PASS')])
    rows=read_csv(p)
    assert rows[0]['page']=='13'
    assert rows[1]['retest']=='PASS'

def test_missing_pdf_leaves_failed_manifest_and_harness(tmp_path):
    import json
    from src.controller import PipelineController
    from src.models import PipelineConfig
    app=tmp_path/'app'; app.mkdir()
    cfg=PipelineConfig(app,app/'missing.pdf',app/'lecture.pdf',app/'output',10)
    assert PipelineController().run(cfg)==1
    manifest=json.loads((app/'output/run_manifest.json').read_text(encoding='utf-8'))
    assert manifest['status']=='FAILED'
    assert manifest['stages']['00']['status']=='FAIL'
    assert (app/'output/HARNESS_LOG.xlsx').is_file()
    assert 'FileNotFoundError' in (app/'logs/errors.log').read_text(encoding='utf-8')

def test_nonrate_unit_also_rejected(inputs,tmp_path):
    from src.io_utils import write_csv,read_csv
    from src.services.extraction import PdfExtractionService
    from src.repositories import DataRepository
    from conftest import APP
    PdfExtractionService().extract(APP/'data/source_assignment.pdf',tmp_path)
    p=tmp_path/'jurisdiction_parameters.csv'; rows=read_csv(p)
    next(r for r in rows if r['parameter_id']=='gamma')['unit']='percent'
    write_csv(p,rows)
    with pytest.raises(ValueError): DataRepository.load(tmp_path)
