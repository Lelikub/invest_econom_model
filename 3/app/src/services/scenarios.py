from dataclasses import replace,asdict
from ..calculators.stress import StressShocksCalculator
from ..calculators.waterfall import CashWaterfallCalculator
from ..calculators.finance import DiscountEffectCalculator
from ..io_utils import write_csv


class ScenarioService:
    def run(self,p,m,s,base,tables):
        stress=StressShocksCalculator.calculate(p,m,s)
        zero=replace(s,oil=0,taiwan=0,tariff=0,term_premium=0,crp_europe=0,
            spread_europe=0,flight=0,crash=0,mu_ebitda=0)
        groups=[('Энергия',('oil',)),('Тайвань',('taiwan',)),('Пошлины',('tariff',)),
            ('Срочная премия',('term_premium',)),('Европа',('crp_europe','spread_europe','flight')),
            ('Обвал tech',('crash',))]
        rows=[dict(scenario='Без шоков',wacc=StressShocksCalculator.calculate(p,m,zero).metrics['wacc'],
            note='All shock magnitudes and EBITDA compression zero')]
        for name,keys in groups:
            diag=replace(zero,**{k:getattr(s,k) for k in keys})
            rows.append(dict(scenario=name,wacc=StressShocksCalculator.calculate(p,m,diag).metrics['wacc'],
                note='Diagnostic only; mu_EBITDA=0 because source assigns only combined compression'))
        rows.append(dict(scenario='Все шоки',wacc=stress.metrics['wacc'],note='Required combined scenario including mu_EBITDA'))
        write_csv(tables/'shock_diagnostics.csv',rows)
        # Full revenue/OPEX split is unknown: preserve revenue in this explicitly
        # illustrative scenario and derive OPEX to reproduce the given EBITDA.
        opex=p.revenue-stress.metrics['ebitda']
        wf=CashWaterfallCalculator.calculate(p.revenue,opex,0,p.debt_service,stress.metrics['dscr'],p.covenant)
        literal=CashWaterfallCalculator.calculate(p.revenue,opex,0,p.debt_service,stress.metrics['dscr'],p.covenant,literal=True)
        for name,result in [('waterfall',wf),('waterfall_literal',literal)]:
            write_csv(tables/f'{name}.csv',result.flows)
        write_csv(tables/'waterfall_summary.csv',[{k:v for k,v in asdict(r).items() if k!='flows'} for r in (wf,literal)])
        discounts=[dict(year=t,base_factor=DiscountEffectCalculator.calculate(base.metrics['wacc'],t),
                        stress_factor=DiscountEffectCalculator.calculate(stress.metrics['wacc'],t)) for t in range(1,11)]
        write_csv(tables/'discount_factors.csv',discounts)
        return stress,wf,literal,rows,discounts
