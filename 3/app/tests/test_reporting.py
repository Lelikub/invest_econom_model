from pathlib import Path
import math
import pytest
from openpyxl import load_workbook
from src.reporting.excel import ExcelGroundTruthWriter, ExcelService, ComparisonService
from src.reporting.charts import ChartValidationService
from src.services.metrics import MetricService
from src.calculators.stress import StressShocksCalculator


def test_excel_contains_independent_formulas_and_sources(inputs,tmp_path):
    p,m,s=inputs; b=MetricService().base(p,m); c=StressShocksCalculator.calculate(p,m,s)
    path=tmp_path/'ground.xlsx'
    refs=ExcelGroundTruthWriter().write(path,p,m,s,b,c,[],[],[],[])
    wb=load_workbook(path,data_only=False)
    assert wb['Base']['B2'].value.startswith('=MAX(')
    assert any('psi_cross' in str(cell.value) for row in wb['Inputs'] for cell in row)
    assert any('*' in str(cell.value) for row in wb['Stress'] for cell in row)
    assert 'stress.wacc' in refs and 'base.wacc' in refs
    assert ComparisonService.reconcile(path,refs,b,c,engine_verified=False)[0]['verification_status']=='NOT_VERIFIED'

def test_missing_excel_worker_is_not_verified(tmp_path):
    status,detail=ExcelService(timeout=3).recalculate(tmp_path/'absent.xlsx')
    assert status=='NOT_VERIFIED' and detail

def test_chart_validation_catches_clipped_label(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6,4)); ax.plot([0,1],[0,1])
    ax.text(1.8,.5,'outside',transform=ax.transAxes)
    r=ChartValidationService.audit(fig,'bad')
    assert r.validation_status=='FAIL'
    plt.close(fig)

def test_chart_validation_accepts_clean_plot():
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    ax.plot([0,1],[0,1]); ax.set(title='Valid',xlabel='x',ylabel='y')
    r=ChartValidationService.audit(fig,'good')
    assert r.validation_status=='PASS'
    plt.close(fig)


def test_numeric_chart_audit_catches_wrong_plotted_series():
    import matplotlib.pyplot as plt
    from src.reporting.charts import ChartValidationService
    fig,ax=plt.subplots()
    line,=ax.plot([0,1],[2,3])
    with pytest.raises(ValueError,match='series'):
        ChartValidationService.match_values(line,[2,4])
    ChartValidationService.match_values(line,[2,3])
    plt.close(fig)


def test_extra_excel_checks_detect_a_broken_identity(tmp_path):
    from openpyxl import Workbook
    from src.models import CalculationResult
    wb=Workbook(); wb.active.title='Checks'; wb.active['B2']=.9
    path=tmp_path/'bad_identity.xlsx'; wb.save(path)
    empty=CalculationResult('base',{})
    rows=ComparisonService.reconcile(path,{'checks.weights':"'Checks'!B2"},empty,empty,True,
        lookup_extra={'checks':{'weights':1}})
    assert len(rows)==1 and rows[0]['verification_status']=='FAIL'
