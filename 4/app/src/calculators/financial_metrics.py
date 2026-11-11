import math
import numpy as np
from ..models import MetricResult

class FinancialMetricsCalculator:
    @staticmethod
    def calculate(cashflows,rate: float) -> MetricResult:
        cf=np.asarray(cashflows,dtype=float)
        if cf.ndim!=1 or not len(cf) or not np.all(np.isfinite(cf)) or not math.isfinite(rate) or rate<=-1:
            raise ValueError('Invalid financial metric inputs')
        pv=cf/(1+rate)**np.arange(len(cf)); npv=float(pv.sum())
        inflows=float(pv[pv>0].sum()); outflows=-float(pv[pv<0].sum())
        # Polynomial in x=1/(1+IRR) finds every finite admissible root.
        nonzero=np.flatnonzero(cf)
        roots=[]
        if len(nonzero)>1 and cf.min()<0<cf.max():
            poly=cf[nonzero[0]:nonzero[-1]+1]/np.max(np.abs(cf))
            for root in np.polynomial.polynomial.polyroots(poly):
                if abs(root.imag)<1e-7 and root.real>0:
                    irr=float(1/root.real-1)
                    residual=float(np.dot(cf,np.power(root.real,np.arange(len(cf)))))
                    if irr>-1 and abs(residual)<=1e-5*np.max(np.abs(cf)) and not any(abs(irr-x)<1e-7 for x in roots): roots.append(irr)
        roots=tuple(sorted(roots)); status='UNIQUE' if len(roots)==1 else 'NO_ROOT' if not roots else 'MULTIPLE_ROOTS'
        cumulative=np.cumsum(pv); dpp=None
        # Requires an initial investment; interpolate within first recovering year.
        if cf[0]<0:
            for t in range(1,len(cf)):
                if cumulative[t]>=-1e-8 and cumulative[t-1]<0 and pv[t]>0:
                    dpp=float(t-1-cumulative[t-1]/pv[t]); break
        return MetricResult(npv,roots[0] if len(roots)==1 else None,status,roots,inflows/outflows if outflows else None,
            inflows,outflows,dpp,'REACHED' if dpp is not None else 'NOT_REACHED')
