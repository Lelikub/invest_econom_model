import numpy as np
import pandas as pd
from scipy.stats import linregress
from ..models import RegressionResult


class MonthlyReturnsCalculator:
    @staticmethod
    def calculate(frame: pd.DataFrame):
        f=frame.set_index('Date')[['HXL','^GSPC']].copy()
        if f.empty: raise ValueError('Empty price sample')
        prices=f.resample('ME').last()
        # A final month is retained only if the final observed day reaches the
        # last weekday of that month. No claim of exchange-calendar completeness.
        last=f.index[-1]
        last_weekday=last+pd.offsets.BMonthEnd(0)
        if last.normalize()<last_weekday.normalize():
            prices=prices.iloc[:-1]
        returns=prices.pct_change(fill_method=None).dropna(how='any')
        return prices,returns


class OLSRegressionCalculator:
    @staticmethod
    def calculate(x,y):
        x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
        if x.ndim!=1 or y.ndim!=1 or len(x)!=len(y) or len(x)<3:
            raise ValueError('OLS requires at least three aligned pairs')
        if not np.isfinite(x).all() or not np.isfinite(y).all() or np.ptp(x)==0:
            raise ValueError('Non-finite/constant OLS benchmark')
        r=linregress(x,y)
        return RegressionResult(float(r.slope),float(r.intercept),float(r.rvalue**2),
            float(r.pvalue),float(r.stderr),float(r.intercept_stderr),len(x))
