from dataclasses import fields
from pathlib import Path
import csv
import math
from .models import ProjectInputData, MarketAssumptions, ShockParameters


class DataRepository:
    @staticmethod
    def load(data_dir: Path) -> tuple[ProjectInputData,MarketAssumptions,ShockParameters]:
        records=[]
        for group,model in [('project',ProjectInputData),('market',MarketAssumptions),('shock',ShockParameters)]:
            with (data_dir/f'{group}_parameters.csv').open(encoding='utf-8-sig',newline='') as stream:
                rows=list(csv.DictReader(stream))
            values={}
            for row in rows:
                key=row['parameter_code']
                if key in values or row['parsing_status']!='PASS' or not row['source_file']:
                    raise ValueError(f'Invalid parameter provenance/duplicate: {key}')
                if key in ('peer','index','name'):
                    values[key]=row['raw_value']
                else:
                    monetary={'capex','revenue','opex','ebitda','debt_service','equity_peer','debt_peer'}
                    fractions={'we','wd','t_nominal','rd_relief','t_floor','s_base','tax_peer','rf','erp','crp',
                        'oil','taiwan','tariff','term_premium','crp_europe','spread_europe','flight','crash','mu_ebitda','gamma1'}
                    expected_unit='million USD' if key in monetary else 'fraction' if key in fractions else 'year' if key=='horizon_years' else 'month' if key=='horizon_months' else 'tonne/year' if key in ('pan_capacity','carbon_capacity') else 'ratio'
                    if row['unit']!=expected_unit:
                        raise ValueError(f'Inconsistent unit for {key}: {row["unit"]}; expected {expected_unit}')
                    values[key]=float(row['numeric_value'])
                    if not math.isfinite(values[key]):
                        raise ValueError(f'Non-finite parameter: {key}')
            allowed={f.name for f in fields(model)}
            if set(values)-allowed:
                raise ValueError(f'Unexpected keys: {set(values)-allowed}')
            records.append(model(**values))
        return tuple(records)
