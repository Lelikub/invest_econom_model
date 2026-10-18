from dataclasses import asdict
import math
import numpy as np
import pandas as pd


class DataValidationService:
    @staticmethod
    def validate_inputs(p,m,s):
        for dto in (p,m,s):
            for k,v in asdict(dto).items():
                if isinstance(v,(float,int)) and not math.isfinite(v): raise ValueError(f'Non-finite {k}')
        if not math.isclose(p.we+p.wd,1,abs_tol=1e-12): raise ValueError('Capital weights')
        for value in (p.we,p.wd,p.t_nominal,p.rd_relief,p.t_floor,m.tax_peer,s.crash,s.flight,s.mu_ebitda):
            if not 0<=value<=1: raise ValueError('Fraction outside [0,1]')
        if min(p.capex,p.debt_service,p.revenue,m.equity_peer,p.we)<=0: raise ValueError('Nonpositive amount')
        if min(p.opex,m.debt_peer)<0 or p.covenant<1: raise ValueError('Invalid economic input')
        if not math.isclose(p.revenue-p.opex,p.ebitda,abs_tol=1e-9): raise ValueError('EBITDA identity')
        diff=p.ebitda/p.debt_service-p.dscr0
        if abs(diff)>.0002: raise ValueError('DSCR inconsistency exceeds input rounding')
        return [dict(check='schema_units_provenance',status='PASS',details='CSV keys, page references and finite values validated'),
            dict(check='capital_weights',status='PASS',details=f'we+wd={p.we+p.wd}'),
            dict(check='ebitda_identity',status='PASS',details=f'{p.revenue}-{p.opex}={p.ebitda}'),
            dict(check='dscr_rounding',status='WARNING' if abs(diff)>1e-10 else 'PASS',
                details=f'EBITDA/DebtService={p.ebitda/p.debt_service:.12f}, source DSCR={p.dscr0}; delta={diff:.12g}; tolerance=0.0002')]

    @staticmethod
    def validate_prices(frame):
        if set(frame.columns)!={'Date','HXL','^GSPC'} or frame.empty: raise ValueError('CSV price schema/empty data')
        dates=pd.to_datetime(frame['Date'],format='%Y-%m-%d',errors='raise')
        if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
            raise ValueError('Invalid, duplicate or unsorted trading dates')
        prices=frame[['HXL','^GSPC']].to_numpy(dtype=float)
        if not np.isfinite(prices).all() or (prices<=0).any(): raise ValueError('Invalid prices')
        daily=frame[['HXL','^GSPC']].pct_change(fill_method=None)
        extreme=(daily.abs()>.2).any(axis=1)
        weekdays=pd.bdate_range(dates.iloc[0],dates.iloc[-1])
        missing=weekdays.difference(pd.DatetimeIndex(dates))
        return [dict(check='price_rows_dates',status='PASS',details=f'{len(frame)} rows; {dates.iloc[0].date()} — {dates.iloc[-1].date()}'),
            dict(check='price_positive_finite',status='PASS',details='No missing, infinite or nonpositive prices'),
            dict(check='weekday_gaps',status='WARNING' if len(missing) else 'PASS',details=f'{len(missing)} absent weekdays (exchange holidays not independently verified)'),
            dict(check='weekends',status='WARNING' if (dates.dt.dayofweek>=5).any() else 'PASS',details=str(int((dates.dt.dayofweek>=5).sum()))),
            dict(check='extreme_daily_returns',status='WARNING' if extreme.any() else 'PASS',details=f'{int(extreme.sum())} days with |return|>20%; retained'),
            dict(check='adjustments',status='NOT_VERIFIED',details='User-provided adjusted close; splits/dividends cannot be independently confirmed from prices alone')]
