from pathlib import Path
import pandas as pd
import pytest
from src.services.extraction import PdfExtractionService, normalize_number
from src.repositories import DataRepository
from src.services.validation import DataValidationService
from src.calculators.regression import MonthlyReturnsCalculator

APP=Path(__file__).resolve().parents[1]
PDF=next((APP.parent/'data').glob('*.pdf'))
PRICES=APP.parent/'data/hxl_gspc_adj_close_5y.csv'

@pytest.fixture(scope='session')
def inputs(tmp_path_factory):
    root=tmp_path_factory.mktemp('pdf_inputs')
    PdfExtractionService().extract(PDF,root)
    return DataRepository.load(root)

@pytest.mark.parametrize('raw,want',[('65,0% (0,65)',.65),('175 б.п.',.0175),
    ('450,00 млн $',450),('5 100 млн $',5100),('+2,50% (+0,025)',.025),
    ('−1,20%',-.012),('1,65x',1.65),('0,10',.1)])
def test_normalization_units(raw,want):
    assert normalize_number(raw)==pytest.approx(want)

def test_actual_pdf_controls_and_provenance(tmp_path):
    rows=PdfExtractionService().extract(PDF,tmp_path)
    p,m,s=DataRepository.load(tmp_path)
    assert p.capex==450 and p.we==.65 and p.wd==.35
    assert p.revenue==150 and p.opex==85 and p.ebitda==65
    assert p.debt_service==39.39 and p.dscr0==1.65 and p.covenant==1.3
    assert m.equity_peer==5100 and m.debt_peer==850 and m.beta_peer==1.25
    assert s.psi_cross==.5 and s.gamma1==.05 and s.psi_tw==2
    assert all(r['source_page'] in range(2,6) for r in rows)
    assert all(r['raw_value'] and r['parsing_status']=='PASS' for r in rows)
    assert len({r['parameter_code'] for r in rows})==len(rows)

def test_input_validation_detects_rounding(inputs):
    audit=DataValidationService.validate_inputs(*inputs)
    assert not any(r['status']=='FAIL' for r in audit)
    assert any(r['check']=='dscr_rounding' and r['status']=='WARNING' for r in audit)

@pytest.mark.parametrize('frame',[
    pd.DataFrame({'Date':['2024-01-01'],'HXL':[1]}),
    pd.DataFrame({'Date':['2024-01-02','2024-01-02'],'HXL':[1,2],'^GSPC':[1,2]}),
    pd.DataFrame({'Date':['2024-01-02'],'HXL':[0],'^GSPC':[1]}),
    pd.DataFrame({'Date':['2024-01-02'],'HXL':[float('inf')],'^GSPC':[1]})])
def test_price_corruption_rejected(frame):
    with pytest.raises(ValueError): DataValidationService.validate_prices(frame)

def test_monthly_alignment_and_incomplete_last_month():
    f=pd.DataFrame({'Date':pd.to_datetime(['2024-01-15','2024-01-31','2024-02-29','2024-03-15']),
        'HXL':[9,10,12,15],'^GSPC':[100,100,110,120]})
    prices,returns=MonthlyReturnsCalculator.calculate(f)
    assert len(prices)==2 and len(returns)==1
    assert returns['HXL'].iloc[0]==pytest.approx(.2)
    assert returns['^GSPC'].iloc[0]==pytest.approx(.1)

def test_missing_month_not_treated_as_one_month_return():
    f=pd.DataFrame({'Date':pd.to_datetime(['2024-01-31','2024-03-29','2024-04-30']),
        'HXL':[10,12,15],'^GSPC':[100,110,120]})
    prices,returns=MonthlyReturnsCalculator.calculate(f)
    assert len(returns)==1
    assert returns['HXL'].iloc[0]==pytest.approx(.25)


def test_csv_unit_mismatch_is_rejected(tmp_path):
    PdfExtractionService().extract(PDF,tmp_path)
    path=tmp_path/'project_parameters.csv'
    frame=pd.read_csv(path)
    frame.loc[frame.parameter_code=='we','unit']='million USD'
    frame.to_csv(path,index=False,encoding='utf-8-sig')
    with pytest.raises(ValueError,match='unit'):
        DataRepository.load(tmp_path)


def test_project_capacities_and_horizon_are_extracted(inputs):
    p,m,s=inputs
    assert p.pan_capacity==10000 and p.carbon_capacity==5000
    assert p.name=='AeroCarbon Synth'
    assert m.horizon_months==60
