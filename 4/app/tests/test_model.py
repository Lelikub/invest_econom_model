from dataclasses import replace
import math
import numpy as np
import pytest

def evaluator():
    from src.services.finance import CrossBorderSupplyChainEvaluator
    return CrossBorderSupplyChainEvaluator()

@pytest.mark.parametrize('code,rate,raw,price', [('DEU',.091,72.10,176.40),('SRB',.171,66.96,165.30),('VNM',.15675,66.96,152.22)])
def test_pdf_controls(inputs,code,rate,raw,price):
    r=evaluator().evaluate(inputs.project,inputs.countries[code])
    assert r.risk.rate == pytest.approx(rate)
    assert r.supply.raw_landed == pytest.approx(raw)
    assert r.supply.price_net == pytest.approx(price)

@pytest.mark.parametrize('code,first,last,draw', [('DEU',4,13,3),('SRB',3,12,2),('VNM',3,13,2)])
def test_calendar(inputs,code,first,last,draw):
    r=evaluator().evaluate(inputs.project,inputs.countries[code]); rows=r.annual
    assert [x.year for x in rows] == list(range(14))
    active=[x for x in rows if x.load>0]
    assert (active[0].year,active[-1].year)==(first,last)
    assert sum(x.load for x in rows)==10
    assert sum(x.depreciation for x in rows)==pytest.approx(r.capex.net)
    assert rows[draw].nwc_cash_effect==-4e6
    assert rows[last].nwc_cash_effect==4e6
    assert sum(x.nwc_cash_effect for x in rows)==0
    assert rows[0].local_cf==-r.capex.net
    if code=='VNM':
        for t in [3,13]:
            assert rows[t].load==.5
            assert rows[t].volume==250000
            assert rows[t].fixed_opex==2500000

@pytest.mark.parametrize('code',['DEU','SRB','VNM'])
def test_identities(inputs,code):
    r=evaluator().evaluate(inputs.project,inputs.countries[code])
    assert r.capex.net==pytest.approx(r.capex.gross-r.capex.subsidy_pv)
    assert r.risk.rate==pytest.approx(inputs.project.wacc+r.risk.crp+r.risk.gpr)
    for a in r.annual:
        assert a.ebit==pytest.approx(a.revenue-a.opex-a.depreciation)
        assert a.local_cf==pytest.approx(a.investment+a.operating_cf+a.nwc_cash_effect)
        assert a.parent_cf==pytest.approx(a.local_cf-a.wht)
        assert a.cash_tax>=0
        assert a.nwc_cash_effect==-a.nwc_change

@pytest.mark.parametrize('oper,nwc,investment,wht,expected',[(100,0,0,.1,90),(-100,0,0,.1,-100),(0,-4,0,.1,-4),(0,4,0,.1,4),(0,0,-220,.1,-220),(100,4,0,.1,94),(100,0,0,0,100)])
def test_wht(oper,nwc,investment,wht,expected):
    from src.calculators.cash_flows import WithholdingTaxCalculator
    assert WithholdingTaxCalculator.parent_cashflow_economic_rule(oper,nwc,investment,wht)==pytest.approx(expected)

def test_literal_pdf_exact_typography():
    from src.calculators.cash_flows import WithholdingTaxCalculator as W
    assert W.parent_cashflow_literal_pdf(-4,4,.1)==pytest.approx(-7.6)
    assert W.parent_cashflow_literal_pdf(104,-4,.1)==108

@pytest.mark.parametrize('ebit,holiday,credit,expected',[(100,0,0,15),(-100,.2,0,0),(100,.298,100,15),(100,.15,0,15)])
def test_cash_tax(ebit,holiday,credit,expected):
    from src.calculators.taxes import FiscalTaxCalculator
    assert FiscalTaxCalculator.cash_tax(ebit,.298,holiday,credit,.15)==pytest.approx(expected)

def test_tax_calendar_and_credit(inputs):
    v=evaluator().evaluate(inputs.project,inputs.countries['VNM'])
    for row in v.annual[3:12]: assert row.holiday_rate==.15
    for row in v.annual[12:14]: assert row.holiday_rate==.20
    s=evaluator().evaluate(inputs.project,inputs.countries['SRB'])
    assert all(a.holiday_rate==.15 for a in s.annual if a.load)
    d=evaluator().evaluate(inputs.project,inputs.countries['DEU'])
    assert d.annual[4].tax_credit==1e6

@pytest.mark.parametrize('field,value',[('approval',0),('clawback',1),('subsidy_rate',0)])
def test_no_subsidy_boundary(inputs,field,value):
    c=replace(inputs.countries['VNM'],**{field:value})
    r=evaluator().evaluate(inputs.project,c)
    assert r.capex.subsidy_pv==0

def test_capex_exemption_and_advance(inputs):
    c=replace(inputs.countries['VNM'],duty_free=1,subsidy_year=0)
    r=evaluator().evaluate(inputs.project,c)
    assert r.capex.gross==pytest.approx(inputs.project.capex_base*(1+c.inflation))
    assert r.capex.subsidy_pv==pytest.approx(r.capex.gross*c.subsidy_rate*c.approval*(1-c.clawback))

def test_metrics_roots_and_payback():
    from src.calculators.financial_metrics import FinancialMetricsCalculator as F
    m=F.calculate([-100,110],.1)
    assert m.npv==pytest.approx(0,abs=1e-10)
    assert m.irr==pytest.approx(.1)
    assert m.pi==pytest.approx(1)
    assert m.dpp==pytest.approx(1)
    assert F.calculate([-100,10],.1).dpp_status=='NOT_REACHED'
    assert F.calculate([1,2],.1).irr_status=='NO_ROOT'
    assert F.calculate([-100,230,-132],.1).irr_status=='MULTIPLE_ROOTS'
    assert F.calculate([-100,0,121],.1).npv==pytest.approx(0,abs=1e-10)

def test_pi_includes_nwc():
    from src.calculators.financial_metrics import FinancialMetricsCalculator as F
    m=F.calculate([-100,-10,150],.1)
    assert m.pv_outflows==pytest.approx(100+10/1.1)

def test_monotonic_risk(inputs):
    c=inputs.countries['VNM']; e=evaluator()
    low=e.evaluate(inputs.project,c); high=e.evaluate(inputs.project,replace(c,igpr=c.igpr+50))
    assert high.risk.rate>low.risk.rate
    assert high.parent.npv<low.parent.npv
    assert [x.revenue for x in low.annual]==[x.revenue for x in high.annual]

def test_scenarios(inputs):
    from src.services.scenarios import ScenarioService
    s=ScenarioService().run(inputs)
    assert set(s.results)=={'A','B','C','ZERO','PILLAR2','STRESS1','STRESS2'}
    assert inputs.countries['VNM'].igpr==200
    assert s.results['STRESS1']['VNM'].risk.rate>s.results['B']['VNM'].risk.rate
    assert s.results['STRESS1']['VNM'].annual[4].opex>s.results['B']['VNM'].annual[4].opex
    assert s.results['STRESS2']['SRB'].annual[3].holiday_rate==.15
    for code,c in inputs.countries.items():
        z=s.results['ZERO'][code]
        assert z.risk.rate==inputs.project.wacc
        assert z.supply.raw_landed==c.raw_base
        assert z.supply.price_net==z.supply.price_weighted
        vals=[s.results[k][code].parent.npv for k in 'ABC']
        st=s.statistics[code]
        assert min(vals)<=st.expected<=max(vals)
        assert st.variance>=0
    for a in s.results['PILLAR2']['VNM'].annual[3:7]:
        if a.ebit>0: assert a.cash_tax/a.ebit>=.15-1e-12

def test_cbam_and_double_count(inputs):
    c=inputs.countries['VNM']; r=evaluator().evaluate(inputs.project,c)
    a=r.annual[4]
    assert a.revenue==pytest.approx(a.volume*(166*(1-.07)-.3*180*.04))
    assert a.opex==pytest.approx(a.volume*62*(1+.03+.05)+5e6)

@pytest.mark.parametrize('changes',[{'approval':1.1},{'duty_free':2},{'share_eu':.9},{'subsidy_year':-1},{'nwc_draw':13},{'wht':10},{'igpr':float('nan')},{'nominal_tax':15}])
def test_reject_invalid_data(inputs,changes):
    from src.services.validation import DataValidationService
    bad=replace(inputs,countries={**inputs.countries,'VNM':replace(inputs.countries['VNM'],**changes)})
    with pytest.raises(ValueError): DataValidationService().validate(bad)

def test_statistical_probabilities():
    from src.calculators.scenario_statistics import ScenarioAggregationCalculator as S
    with pytest.raises(ValueError): S.calculate([1,2],[.2,.3])
    with pytest.raises(ValueError): S.calculate([1,2],[-.1,1.1])
    assert S.calculate([10,20,30],[.2,.5,.3]).expected==21
