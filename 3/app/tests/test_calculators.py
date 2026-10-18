from dataclasses import replace
import numpy as np
import pytest

from src.calculators.finance import (EffectiveTaxCalculator, LeverageCalculator,
    HamadaBetaCalculator, CAPMCalculator, CostOfDebtCalculator, WACCCalculator,
    CreditSpreadCalculator, DSCRCalculator, DiscountEffectCalculator, MissingDefaultParameters)
from src.calculators.regression import OLSRegressionCalculator, MonthlyReturnsCalculator
from src.calculators.stress import StressShocksCalculator
from src.calculators.waterfall import CashWaterfallCalculator
from src.services.metrics import MetricService


@pytest.mark.parametrize('nominal,relief,floor,want',[(.19,.04,.15,.15),(.1,.04,.15,.15),(.3,.04,.15,.26)])
def test_effective_tax_floor(nominal,relief,floor,want):
    assert EffectiveTaxCalculator.calculate(nominal,relief,floor)==pytest.approx(want)

def test_hamada_hand_checked_and_all_equity():
    assert HamadaBetaCalculator.unlever(1.2,.2,.5)==pytest.approx(6/7)
    assert HamadaBetaCalculator.relever(1.2,.2,.5)==pytest.approx(1.68)
    assert HamadaBetaCalculator.relever(1.2,.2,0)==1.2

@pytest.mark.parametrize('debt,equity',[(1,0),(-1,1),(1,float('nan'))])
def test_invalid_leverage_rejected(debt,equity):
    with pytest.raises(ValueError): LeverageCalculator.calculate(debt,equity)

def test_capm_beta_zero_and_normal():
    assert CAPMCalculator.calculate(.04,0,.05,.01)==pytest.approx(.05)
    assert CAPMCalculator.calculate(.04,1.2,.05,.01)==pytest.approx(.11)

def test_debt_no_tax_and_normal():
    assert CostOfDebtCalculator.after_tax(.06,0)==.06
    assert CostOfDebtCalculator.after_tax(.06,.15)==pytest.approx(.051)

def test_wacc_normal_and_all_equity():
    assert WACCCalculator.calculate(.6,.4,.12,.05)==pytest.approx(.092)
    assert WACCCalculator.calculate(1,0,.12,.05)==.12
    with pytest.raises(ValueError): WACCCalculator.calculate(.6,.6,.12,.05)

@pytest.mark.parametrize('dscr,want',[(1.300001,0),(1.3,0),(1.299999,.05*(1.3/1.299999-1)),(1,.015),(1.155,.00627705627705628)])
def test_credit_piecewise_thresholds(dscr,want):
    assert CreditSpreadCalculator.calculate(dscr,1.3,.05)==pytest.approx(want,abs=1e-12)

def test_default_without_parameters_is_blocked():
    with pytest.raises(MissingDefaultParameters): CreditSpreadCalculator.calculate(.9999,1.3,.05)
    assert CreditSpreadCalculator.calculate(.9,1.3,.05,2,.1,.02)==pytest.approx(.22)

def test_dscr_and_discount():
    assert DSCRCalculator.calculate(1.65,.3)==pytest.approx(1.155)
    assert DiscountEffectCalculator.calculate(.1,10)==pytest.approx(.3855432894295314)
    assert DiscountEffectCalculator.calculate(0,10)==1
    with pytest.raises(ValueError): DiscountEffectCalculator.calculate(-1,10)

def test_regression_known_line():
    x=np.array([-.2,-.1,0,.1,.2]); y=.01+1.5*x
    r=OLSRegressionCalculator.calculate(x,y)
    assert r.beta_ols==pytest.approx(1.5)
    assert r.alpha_raw==pytest.approx(.01)
    assert r.r_squared==pytest.approx(1)
    assert r.alpha_jensen is None

@pytest.mark.parametrize('x,y',[([],[]),([1,1,1],[1,2,3]),([1,2,3],[1,2]),([1,2,float('nan')],[1,2,3])])
def test_regression_bad_sample_rejected(x,y):
    with pytest.raises(ValueError): OLSRegressionCalculator.calculate(x,y)

def test_stress_all_zero_matches_base(inputs):
    p,m,s=inputs
    s=replace(s,oil=0,taiwan=0,tariff=0,term_premium=0,crp_europe=0,
              spread_europe=0,flight=0,crash=0,mu_ebitda=0)
    b=MetricService().base(p,m).metrics
    stress=StressShocksCalculator.calculate(p,m,s).metrics
    for k in ('rf','beta_u','beta_l','de','we','wd','erp','crp','ke','kd','kd_after_tax','wacc','dscr'):
        assert stress[k]==pytest.approx(b[k])

def test_combined_stress_keeps_cross_effects_and_crash_erp(inputs):
    p,m,s=inputs; r=StressShocksCalculator.calculate(p,m,s).metrics
    assert r['delta_total']==pytest.approx(.4)
    assert r['rf']==pytest.approx(.104)
    assert r['erp']==pytest.approx(.0605)
    assert r['dscr']==pytest.approx(1.155)
    assert r['beta_multiplier']==pytest.approx(1.285)
    assert r['we']+r['wd']==pytest.approx(1)
    assert r['de']==pytest.approx(35/39)
    assert r['credit_spread']==pytest.approx(.00627705627705628)

def test_equity_collapse_rejected(inputs):
    p,m,s=inputs
    with pytest.raises(ValueError): StressShocksCalculator.calculate(p,m,replace(s,crash=.95,flight=.05))

@pytest.mark.parametrize('dscr,locked',[(1.299999,True),(1.3,False),(1.300001,False)])
def test_waterfall_lockup_never_cancels_debt(dscr,locked):
    r=CashWaterfallCalculator.calculate(150,104.5,0,39.39,dscr,1.3)
    assert r.dividend_lockup is locked
    assert r.debt_service==39.39
    assert r.cash_after_debt_service==pytest.approx(6.11)
    assert sum(row['amount'] for row in r.flows)==pytest.approx(r.retained)
    assert r.dividends==(0 if locked else pytest.approx(6.11))

def test_waterfall_insufficient_cash_records_shortfall():
    r=CashWaterfallCalculator.calculate(10,5,1,8,.7,1.3)
    assert r.debt_service==8
    assert r.debt_paid==4
    assert r.shortfall==4
    assert r.retained==0

def test_waterfall_literal_is_separate():
    r=CashWaterfallCalculator.calculate(150,104.5,0,39.39,1.155,1.3,literal=True)
    assert r.debt_service==39.39
    assert r.debt_paid==0
    assert r.dsra==45.5
