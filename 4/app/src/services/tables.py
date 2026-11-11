"""Export one canonical set of calculation tables for charts and documents."""
from dataclasses import asdict,replace
from ..io_utils import write_csv,write_json
from .finance import CrossBorderSupplyChainEvaluator

class TableService:
    def write(self,inputs,scenarios,directory):
        directory.mkdir(parents=True,exist_ok=True)
        base=scenarios.results['B']; frames={}
        def table(name,rows):
            rows=list(rows); write_csv(directory/(name+'.csv'),rows); frames[name]=rows
        table('risk_rates',[dict(country=c,wacc=inputs.project.wacc,**asdict(r.risk)) for c,r in base.items()])
        table('capex',[dict(country=c,**asdict(r.capex)) for c,r in base.items()])
        table('supply_chains',[dict(country=c,raw_base=r.country.raw_base,**asdict(r.supply),lead_days=r.country.lead_days,
            share_eu=r.country.share_eu,share_asia=r.country.share_asia,logistics_in=r.country.logistics_in,logistics_out=r.country.logistics_out) for c,r in base.items()])
        table('annual_cashflows',[dict(country=c,**asdict(a)) for c,r in base.items() for a in r.annual])
        table('all_scenario_cashflows',[dict(scenario=s,country=c,**asdict(a)) for s,rs in scenarios.results.items() for c,r in rs.items() for a in r.annual])
        table('time_schedule',[dict(country=c,year=a.year,load=a.load,volume=a.volume,nwc_cash_effect=a.nwc_cash_effect,depreciation=a.depreciation) for c,r in base.items() for a in r.annual])
        table('taxation',[dict(country=c,year=a.year,load=a.load,ebit=a.ebit,holiday_rate=a.holiday_rate,tax_credit=a.tax_credit,cash_tax=a.cash_tax,literal_tax=a.literal_tax) for c,r in base.items() for a in r.annual])
        metricrows=[]
        for s,rs in scenarios.results.items():
            for c,r in rs.items():
                for scope in ('local','parent','literal','literal_tax'):
                    metricrows.append(dict(scenario=s,country=c,scope=scope,**asdict(getattr(r,scope))))
        table('all_metrics',metricrows)
        table('base_metrics',[row for row in metricrows if row['scenario']=='B' and row['scope'] in ('local','parent')])
        table('scenario_metrics',[row for row in metricrows if row['scenario'] in ('A','B','C') and row['scope']=='parent'])
        table('scenario_statistics',[dict(country=c,**asdict(s)) for c,s in scenarios.statistics.items()])
        table('source_sensitivity',[dict(country=c,economic_npv=r.parent.npv,literal_wht_npv=r.literal.npv,
            literal_wht_delta=r.literal.npv-r.parent.npv,literal_tax_npv=r.literal_tax.npv,literal_tax_delta=r.literal_tax.npv-r.parent.npv,
            local_npv=r.local.npv,wht_npv_cost=r.local.npv-r.parent.npv) for c,r in base.items()])
        stress=[]; deltas=[]
        for name,c in [('STRESS1','VNM'),('STRESS2','SRB')]:
            b=base[c]; r=scenarios.results[name][c]
            stress.append(dict(stress=name,country=c,base_npv=b.parent.npv,stress_npv=r.parent.npv,delta=r.parent.npv-b.parent.npv,
                base_rate=b.risk.rate,stress_rate=r.risk.rate,base_opex=b.annual[4].opex,stress_opex=r.annual[4].opex,
                base_lead_days=b.country.lead_days,stress_lead_days=r.country.lead_days))
            for group,bd,rd in [('country',asdict(b.country),asdict(r.country)),('risk',asdict(b.risk),asdict(r.risk)),('capex',asdict(b.capex),asdict(r.capex)),('supply',asdict(b.supply),asdict(r.supply)),('parent',asdict(b.parent),asdict(r.parent))]:
                for key,value in bd.items():
                    if not isinstance(value,(float,int)) or not isinstance(rd[key],(float,int)): continue
                    delta=rd[key]-value
                    deltas.append(dict(stress=name,country=c,metric=group+'.'+key,base=value,stress_value=rd[key],absolute_change=delta,relative_change=delta/abs(value) if value else None,reason='PDF14 prescribed scenario'))
            for ba,ra in zip(b.annual,r.annual):
                for key in asdict(ba):
                    value=getattr(ba,key); changed=getattr(ra,key); delta=changed-value
                    deltas.append(dict(stress=name,country=c,metric=f'year{ba.year}.{key}',base=value,stress_value=changed,absolute_change=delta,relative_change=delta/abs(value) if value else None,reason='Full recalculation'))
        table('stress_metrics',stress); table('stress_deltas',deltas)
        table('scenario_inputs',[dict(scenario=s,**asdict(r.country)) for s,rs in scenarios.results.items() for r in rs.values()])
        # Finite, explicitly scoped sensitivities; no macro risk haircut on revenue.
        e=CrossBorderSupplyChainEvaluator(); sensitivities=[]
        for code,c in inputs.countries.items():
            for parameter,grid in [('igpr',[-50.,0.,50.,100.]),('wht',[0.,.05,.10,.15]),('cbam',[0.,.04,.08,.12]),('delay_year',[0.,1.,2.])]:
                for x in grid:
                    p=inputs.project
                    if parameter=='igpr': altered=replace(c,igpr=max(0,c.igpr+x))
                    elif parameter in ('wht','cbam'): altered=replace(c,**{parameter:x})
                    else:
                        altered=replace(c,first=c.first+x,last=c.last+x,nwc_draw=c.nwc_draw+x,nwc_release=c.nwc_release+x,holiday_end=c.holiday_end+x)
                        p=replace(p,calendar_end=p.calendar_end+x)
                    result=e.evaluate(p,altered)
                    sensitivities.append(dict(country=code,parameter=parameter,x=x,parent_npv=result.parent.npv,unit_x='index increment' if parameter=='igpr' else 'year' if parameter=='delay_year' else 'fraction',definition='Shift operating/NWC/tax calendar; grant PV and CF0 fixed' if parameter=='delay_year' else 'One input changed; all others fixed'))
        table('sensitivities',sensitivities)
        # IQR diagnostics preserve every scenario; an outlier is not automatically an error.
        import numpy as np
        values=np.array([r['npv'] for r in metricrows if r['scope']=='parent'],dtype=float)
        q1,q3=np.quantile(values,[.25,.75]); spread=q3-q1
        table('outlier_diagnostics',[dict(scenario=r['scenario'],country=r['country'],parent_npv=r['npv'],
            lower_fence=float(q1-1.5*spread),upper_fence=float(q3+1.5*spread),
            diagnostic='IQR_OUTLIER_RETAINED' if r['npv']<q1-1.5*spread or r['npv']>q3+1.5*spread else 'WITHIN_IQR_FENCES',
            action='RETAINED; includes valid edge/stress cases') for r in metricrows if r['scope']=='parent'])
        return frames
