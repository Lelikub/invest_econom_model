from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
from ..calculators.regression import MonthlyReturnsCalculator,OLSRegressionCalculator
from ..models import MarketPriceSeries
from ..io_utils import sha256,write_csv
from .validation import DataValidationService


class MarketDataService:
    def process(self,path: Path,tables: Path):
        frame=pd.read_csv(path)
        audit=DataValidationService.validate_prices(frame)
        frame['Date']=pd.to_datetime(frame['Date'],format='%Y-%m-%d')
        series=MarketPriceSeries(frame,path,sha256(path))
        monthly,returns=MonthlyReturnsCalculator.calculate(frame)
        if len(returns)<3: raise ValueError('Insufficient full-month paired returns')
        r=OLSRegressionCalculator.calculate(returns['^GSPC'],returns.HXL)
        monthly.to_csv(tables/'monthly_prices.csv',encoding='utf-8-sig',index_label='Date')
        returns.to_csv(tables/'monthly_returns.csv',encoding='utf-8-sig',index_label='Date')
        write_csv(tables/'ols_summary.csv',[asdict(r)])
        residual=returns.HXL-r.alpha_raw-r.beta_ols*returns['^GSPC']
        x=returns['^GSPC']; leverage=1/len(x)+(x-x.mean())**2/((x-x.mean())**2).sum()
        loo=[]
        for i in range(len(returns)):
            keep=np.arange(len(returns))!=i
            loo.append(OLSRegressionCalculator.calculate(x.iloc[keep],returns.HXL.iloc[keep]).beta_ols)
        diag=pd.DataFrame({'HXL':returns.HXL,'market':x,'residual':residual,
            'leverage':leverage,'beta_without_observation':loo,'beta_influence':np.asarray(loo)-r.beta_ols})
        diag.to_csv(tables/'ols_diagnostics.csv',encoding='utf-8-sig',index_label='Date')
        dates=frame.groupby(frame.Date.dt.to_period('M')).Date.agg(['min','max','count'])
        dates['status']=['INCLUDED_PRICE' if period.to_timestamp('M') in monthly.index else 'EXCLUDED_INCOMPLETE_FINAL' for period in dates.index]
        dates.to_csv(tables/'monthly_observation_audit.csv',encoding='utf-8-sig',index_label='month')
        daily=frame.set_index('Date')[['HXL','^GSPC']].pct_change(fill_method=None)
        daily[(daily.abs()>.2).any(axis=1)].to_csv(tables/'extreme_daily_returns.csv',encoding='utf-8-sig',index_label='Date')
        audit.append(dict(check='monthly_sample',status='PASS',details=f'{len(monthly)} monthly prices, {len(returns)} returns; last incomplete month excluded; first month provides only initial month-end price'))
        audit.append(dict(check='ols_influence',status='WARNING',details=f'Max leave-one-out beta deviation={diag.beta_influence.abs().max():.8f}; observations retained'))
        return series,monthly,returns,r,audit
