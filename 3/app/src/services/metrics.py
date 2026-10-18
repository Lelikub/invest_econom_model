from ..models import CalculationResult
from ..calculators.finance import (EffectiveTaxCalculator,LeverageCalculator,
    HamadaBetaCalculator,CAPMCalculator,CostOfDebtCalculator,WACCCalculator)


class MetricService:
    @staticmethod
    def beta_comparison(regression,market):
        delta=regression.beta_ols-market.beta_peer
        return [dict(beta_ols=regression.beta_ols,beta_theoretical=market.beta_peer,
            signed_difference=delta,absolute_difference=abs(delta),relative_difference=abs(delta)/abs(market.beta_peer))]

    @staticmethod
    def metric_comparison(base,stress,units):
        return [dict(metric_id=k,base=base.metrics[k],stress=v,change=v-base.metrics[k],unit=units[k]) for k,v in stress.metrics.items()]

    @staticmethod
    def taiwan_sensitivity(stress,shock):
        values=stress.metrics
        alternative_ke=values['ke']-shock.taiwan
        return [dict(scenario='CRP_Taiwan=GPR_Taiwan',ke=values['ke'],wacc=values['wacc']),
            dict(scenario='CRP_Taiwan omitted (diagnostic alternative)',ke=alternative_ke,
                wacc=WACCCalculator.calculate(values['we'],values['wd'],alternative_ke,values['kd_after_tax']))]

    @staticmethod
    def verification_lookup(discount,decomposition):
        return {
            'discount_base':{f'year_{r["year"]}':r['base_factor'] for r in discount},
            'discount_stress':{f'year_{r["year"]}':r['stress_factor'] for r in discount},
            'decomposition':{key:row['delta'] for key,row in zip(('Ke','Kd_net','weights'),decomposition)},
            'checks':dict(base_weights=1,stress_weights=1,delta_valid=True,ebitda=0,waterfall_balance=0)}

    def base(self,p,m):
        tax=EffectiveTaxCalculator.calculate(p.t_nominal,p.rd_relief,p.t_floor)
        de_peer=LeverageCalculator.calculate(m.debt_peer,m.equity_peer)
        bu=HamadaBetaCalculator.unlever(m.beta_peer,m.tax_peer,de_peer)
        de=LeverageCalculator.calculate(p.wd,p.we)
        bl=HamadaBetaCalculator.relever(bu,tax,de)
        ke=CAPMCalculator.calculate(m.rf,bl,m.erp,m.crp)
        kd=CostOfDebtCalculator.calculate(m.rf,p.s_base)
        net=CostOfDebtCalculator.after_tax(kd,tax)
        return CalculationResult('base',dict(t_eff=tax,de_peer=de_peer,beta_u=bu,de=de,beta_l=bl,
            rf=m.rf,erp=m.erp,crp=m.crp,we=p.we,wd=p.wd,ke=ke,kd=kd,kd_after_tax=net,
            wacc=WACCCalculator.calculate(p.we,p.wd,ke,net),dscr=p.dscr0,
            equity=p.capex*p.we,debt=p.capex*p.wd,ebitda=p.ebitda,credit_spread=0.,delta_total=0.,pi_exp=0.,beta_multiplier=1.))

    @staticmethod
    def decomposition(base,stress):
        b=base.metrics; s=stress.metrics
        return [dict(component='Стоимость собственного капитала',delta=b['we']*(s['ke']-b['ke'])),
            dict(component='Стоимость долга после налога',delta=b['wd']*(s['kd_after_tax']-b['kd_after_tax'])),
            dict(component='Изменение весов (при стрессовых ставках)',delta=(s['we']-b['we'])*s['ke']+(s['wd']-b['wd'])*s['kd_after_tax'])]
