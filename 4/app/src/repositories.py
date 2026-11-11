"""Strict CSV → immutable DTO boundary."""
from dataclasses import fields
from .models import Project, Country, Inputs
from .io_utils import read_csv

FILES=('project_constants','jurisdiction_parameters','subsidy_parameters','supply_chains','market_allocations','time_indexing','tax_policies','scenarios')

class DataRepository:
    @staticmethod
    def load(directory):
        rows=[r for file in FILES for r in read_csv(directory/(file+'.csv'))]
        values={}; keys=set()
        for r in rows:
            key=(r['jurisdiction'],r['parameter_id'])
            if key in keys: raise ValueError(f'Duplicate CSV parameter {key}')
            keys.add(key)
            if not r['original_text'] or r['parse_status']!='PARSED' or int(r['source_page']) not in range(1,16):
                raise ValueError('Missing parameter provenance')
            field=r['parameter_id']; unit=r['unit']
            fraction={'spread','gpr_base','nominal_tax','inflation','subsidy_rate','approval','clawback','equip_duty','gov_rate','wht','logistics_in','input_duty','share_eu','share_asia','logistics_out','cbam','holiday_tax','first_load','last_load','wacc','pillar_floor'}
            if field in fraction and unit!='fraction': raise ValueError(f'Invalid unit for {field}: {unit}')
            specific={
                'gamma':'fraction/sigma','oecd':'index','igpr':'index','igpr_mean':'index','igpr_sigma':'index','volatility':'ratio',
                'capex_base':'USD','nwc':'USD','volume':'m2/year','fixed_opex':'USD/year','tax_credit':'USD/year','duty_free':'indicator',
                'lead_days':'day','outbound_days':'day','vnm_days':'day','vnm_igpr':'index',
                **{k:'year' for k in ('delay','subsidy_year','first','last','nwc_draw','nwc_release','holiday_end','years','calendar_end')},
                **{k:'USD/m2' for k in ('raw_base','raw_control','price_control','net_price_control','price_eu','price_asia')},
                **{k:'fraction' for k in ('p_A','p_B','p_C','integration_reduction','vnm_freight','srb_cbam','deu_igpr_increase','deu_inflation')}}
            if field not in fraction and (field not in specific or unit!=specific[field]): raise ValueError(f'Invalid or unknown unit for {field}: {unit}')
            values[key]=float(r['value'])
        def get(country,cls):
            return {f.name:values[(country,f.name)] for f in fields(cls) if f.name!='code'}
        try:
            project=Project(**get('ALL',Project))
            countries={c:Country(code=c,**get(c,Country)) for c in ('DEU','SRB','VNM')}
        except KeyError as e: raise ValueError(f'Missing mandatory CSV parameter {e}') from e
        scenarios={r['parameter_id']:float(r['value']) for r in rows if r['period_or_scenario']=='SCENARIO'}
        return Inputs(project,countries,scenarios,tuple(rows))
