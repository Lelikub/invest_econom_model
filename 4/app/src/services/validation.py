from dataclasses import asdict
import math
from ..calculators.operating_costs import TariffAndLogisticsCalculator

class DataValidationService:
    def validate(self,inputs):
        p=inputs.project; audit=[]
        for key,value in asdict(p).items():
            if not math.isfinite(value) or value<0: raise ValueError(f'Invalid project {key}')
        if min(p.years,p.igpr_sigma,p.capex_base)<=0 or p.wacc<=-1 or p.wacc>1: raise ValueError('Invalid project scale')
        for code,c in inputs.countries.items():
            for key,value in asdict(c).items():
                if key=='code': continue
                if not math.isfinite(value) or value<0: raise ValueError(f'Invalid {code}.{key}')
                if key in {'spread','gpr_base','gamma','nominal_tax','inflation','subsidy_rate','approval','clawback','equip_duty','gov_rate','wht','logistics_in','input_duty','share_eu','share_asia','logistics_out','cbam','holiday_tax','first_load','last_load'} and value>1: raise ValueError(f'Rate outside [0,1]: {key}')
                if key in {'first','last','nwc_draw','nwc_release','subsidy_year','holiday_end','oecd'} and value!=int(value): raise ValueError(f'Noninteger year/index {key}')
            if c.duty_free not in (0,1) or c.oecd>7: raise ValueError('Invalid categorical indicator')
            if not math.isclose(c.share_eu+c.share_asia,1,abs_tol=1e-12): raise ValueError('Market shares must sum to one')
            if c.nwc_draw!=c.first-1 or c.nwc_release!=c.last or c.last<c.first or c.subsidy_year>c.last: raise ValueError('Invalid NWC/subsidy calendar')
            if not math.isclose((c.last-c.first-1)+c.first_load+c.last_load,p.years): raise ValueError('Calendar must sum to equivalent operating horizon')
            supply=TariffAndLogisticsCalculator.calculate(p,c)
            for metric,expected in [('raw_landed',c.raw_control),('price_weighted',c.price_control),('price_net',c.net_price_control)]:
                value=getattr(supply,metric)
                if not math.isclose(value,expected,abs_tol=.005): raise ValueError(f'SOURCE/PARSING mismatch {code} {metric}: {value} vs {expected}')
                audit.append(dict(check=f'{code}.{metric}',status='PASS',value=value,expected=expected,unit='USD/m2'))
        if not math.isclose(sum(inputs.scenarios['p_'+k] for k in 'ABC'),1,abs_tol=1e-12): raise ValueError('Scenario probabilities do not sum to one')
        if any(not 0<=inputs.scenarios['p_'+k]<=1 for k in 'ABC'): raise ValueError('Invalid probability')
        return audit
