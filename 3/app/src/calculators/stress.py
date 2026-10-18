from ..models import StressResult
from ..services.metrics import MetricService
from .finance import (LeverageCalculator,HamadaBetaCalculator,CAPMCalculator,
    CostOfDebtCalculator,WACCCalculator,DSCRCalculator,CreditSpreadCalculator,fraction)


class StressShocksCalculator:
    @staticmethod
    def calculate(p,m,s):
        b=MetricService().base(p,m).metrics
        delta=s.crash+s.flight
        fraction(delta)
        if delta>=1: raise ValueError('Capitalization collapse: delta_total>=1')
        pi=s.eta*s.oil
        rf=m.rf+pi+s.term_premium+s.alpha_cross*s.taiwan
        multiplier=1+s.psi_tariff*s.tariff+s.psi_energy*s.oil+s.psi_cross*s.tariff*s.oil+s.psi_tw*s.taiwan
        bu=b['beta_u']*multiplier
        equity=b['equity']*(1-delta); debt=b['debt']
        de=LeverageCalculator.calculate(debt,equity)
        we=equity/(equity+debt); wd=1-we
        bl=HamadaBetaCalculator.relever(bu,b['t_eff'],de)
        erp=m.erp+s.panic_lambda*s.crash
        crp=m.crp+s.crp_europe+s.taiwan
        ke=CAPMCalculator.calculate(rf,bl,erp,crp)
        dscr=DSCRCalculator.calculate(p.dscr0,s.mu_ebitda)
        spread=CreditSpreadCalculator.calculate(dscr,p.covenant,s.gamma1)
        kd=CostOfDebtCalculator.calculate(rf,p.s_base,s.spread_europe,spread)
        net=CostOfDebtCalculator.after_tax(kd,b['t_eff'])
        return StressResult('stress',dict(t_eff=b['t_eff'],de_peer=b['de_peer'],rf=rf,pi_exp=pi,
            beta_multiplier=multiplier,beta_u=bu,delta_total=delta,equity=equity,debt=debt,de=de,
            we=we,wd=wd,beta_l=bl,erp=erp,crp=crp,ke=ke,dscr=dscr,credit_spread=spread,
            kd=kd,kd_after_tax=net,wacc=WACCCalculator.calculate(we,wd,ke,net),ebitda=p.ebitda*(1-s.mu_ebitda)))
