"""Independent Excel equations. Never inject calculated Python values into cells."""
from dataclasses import asdict,fields
from pathlib import Path
import os
import subprocess
import sys
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter as col
from openpyxl.workbook.properties import CalcProperties
from ..models import AnnualResult

class ExcelGroundTruthWriter:
    def write(self,path,inputs,scenarios):
        wb=Workbook(); wb.remove(wb.active); self.wb=wb; self.refs=[]
        def sheet(name,headers):
            ws=wb.create_sheet(name); ws.append(headers); return ws
        source=sheet('Sources',['parameter','country','period','value','unit','source','page','original_text'])
        for r in inputs.provenance:
            source.append([r[k] for k in ('parameter_id','jurisdiction','period_or_scenario','value','unit','source_file','source_page','original_text')])
        base=sheet('Inputs',['country','parameter','value','unit']); base_refs={}
        for r in inputs.provenance:
            if r['period_or_scenario']!='BASE': continue
            base.append([r['jurisdiction'],r['parameter_id'],float(r['value']),r['unit']])
            base_refs[(r['jurisdiction'],r['parameter_id'])]=f"Inputs!$C${base.max_row}"
        sc=sheet('Scenario_Definitions',['parameter','value','unit','source_page']); sc_refs={}
        for r in inputs.provenance:
            if r['period_or_scenario']=='SCENARIO':
                sc.append([r['parameter_id'],float(r['value']),r['unit'],r['source_page']]); sc_refs[r['parameter_id']]=f"Scenario_Definitions!$B${sc.max_row}"
        si=sheet('Scenario_Inputs',['scenario','country','parameter','value']); param={}
        project={k:base_refs[('ALL',k)] for k in asdict(inputs.project)}
        for scenario,countries in scenarios.results.items():
            for code,c in inputs.countries.items():
                for key in asdict(c):
                    if key=='code': continue
                    original=base_refs[(code,key)]; expr=original
                    if scenario=='A':
                        if key=='igpr': expr=f"{original}*(1-{sc_refs['integration_reduction']})"
                        if key in ('equip_duty','input_duty','cbam'): expr='0'
                    if scenario=='ZERO' and key in ('spread','gpr_base','gamma','equip_duty','input_duty','cbam','logistics_in','logistics_out'): expr='0'
                    if scenario=='PILLAR2' and code=='VNM':
                        if key=='holiday_tax': expr='0'
                        if key=='holiday_end': expr=base_refs[(code,'first')]+'+3'
                    if scenario in ('C','STRESS1') and code=='VNM' and key in ('igpr','logistics_in','lead_days'):
                        expr=sc_refs[{'igpr':'vnm_igpr','logistics_in':'vnm_freight','lead_days':'vnm_days'}[key]]
                    if scenario in ('C','STRESS2') and code=='SRB' and key=='cbam': expr=sc_refs['srb_cbam']
                    if scenario=='C' and code=='DEU':
                        if key=='igpr': expr=f"{original}*(1+{sc_refs['deu_igpr_increase']})"
                        if key=='inflation': expr=sc_refs['deu_inflation']
                    si.append([scenario,code,key,'='+expr]); param[(scenario,code,key)]=f"Scenario_Inputs!$D${si.max_row}"
        risks=sheet('Risk_Rates',['scenario','country','CRP','GPR','r_adj'])
        capex=sheet('CAPEX_Subsidies',['scenario','country','gross_USD','subsidy_PV_USD','net_USD'])
        supply=sheet('Supply_Chains',['scenario','country','price_weighted','raw_landed','price_net','cbam_unit','inbound_unit','duty_unit','outbound_unit'])
        timeline=sheet('Time_Schedule',['scenario','country','year','load','NWC_change'])
        taxation=sheet('Taxation',['scenario','country','year','holiday_rate','tax_credit'])
        metrics=sheet('Financial_Metrics',['scenario','country','scope','NPV_USD','IRR','IRR_status','PI','PV_in_USD','PV_out_USD','DPP_year','DPP_status'])
        annual_fields=[f.name for f in fields(AnnualResult)]
        metrics_refs={}
        for scenario,countries in scenarios.results.items():
            for code,result in countries.items():
                c={key:param[(scenario,code,key)] for key in asdict(result.country) if key!='code'}
                rr=risks.max_row+1
                formulas=[f"{c['spread']}*{c['volatility']}",f"{c['gpr_base']}+{c['gamma']}*MAX(0,({c['igpr']}-{project['igpr_mean']})/{project['igpr_sigma']})",f"{project['wacc']}+C{rr}+D{rr}"]
                risks.append([scenario,code,*['='+v for v in formulas]])
                risk_refs={key:f'Risk_Rates!{col(i)}{rr}' for i,key in enumerate(('crp','gpr','rate'),3)}
                for key,ref in risk_refs.items(): self.bind(ref,getattr(result.risk,key),key,code,scenario,unit='fraction',formula='RISK')
                cr=capex.max_row+1
                capex.append([scenario,code,f"={project['capex_base']}*(1+{c['inflation']})*(1+{c['equip_duty']}*(1-{c['duty_free']}))",
                    f"=C{cr}*{c['subsidy_rate']}*{c['approval']}*(1-{c['clawback']})/(1+{c['gov_rate']})^{c['subsidy_year']}",f'=C{cr}-D{cr}'])
                cap_refs={key:f'CAPEX_Subsidies!{col(i)}{cr}' for i,key in enumerate(('gross','subsidy_pv','net'),3)}
                for key,ref in cap_refs.items(): self.bind(ref,getattr(result.capex,key),key,code,scenario,formula='CAPEX')
                sr=supply.max_row+1
                supply.append([scenario,code,f"={c['share_eu']}*{project['price_eu']}+{c['share_asia']}*{project['price_asia']}",
                    f"={c['raw_base']}*(1+{c['input_duty']}+{c['logistics_in']})",f'=C{sr}-F{sr}-I{sr}',
                    f"={c['share_eu']}*{project['price_eu']}*{c['cbam']}",f"={c['raw_base']}*{c['logistics_in']}",
                    f"={c['raw_base']}*{c['input_duty']}",f"=C{sr}*{c['logistics_out']}"])
                su_refs={key:f'Supply_Chains!{col(i)}{sr}' for i,key in enumerate(asdict(result.supply),3)}
                for key,ref in su_refs.items(): self.bind(ref,getattr(result.supply,key),key,code,scenario,unit='USD/m2',formula='SUPPLY')
                name=f'Cashflows_{code}' if scenario=='B' else f'{scenario}_{code}'
                cf=sheet(name,annual_fields+['local_PV','literal_PV','literal_tax_PV',
                    'local_cum','literal_cum','literal_tax_cum','parent_DPP','local_DPP','literal_DPP','literal_tax_DPP'])
                n=len(result.annual)+1
                columns={key:col(i) for i,key in enumerate(annual_fields,1)}
                for row in result.annual:
                    t=row.year; r=t+2; tr=timeline.max_row+1; tx=taxation.max_row+1
                    timeline.append([scenario,code,t,
                        f"=IF(OR(C{tr}<{c['first']},C{tr}>{c['last']}),0,IF(C{tr}={c['first']},{c['first_load']},IF(C{tr}={c['last']},{c['last_load']},1)))",
                        f"=IF(C{tr}={c['nwc_draw']},{project['nwc']},IF(C{tr}={c['nwc_release']},-{project['nwc']},0))"])
                    taxation.append([scenario,code,t,f"=IF(C{tx}<={c['holiday_end']},{c['holiday_tax']},{c['nominal_tax']})",f"={c['tax_credit']}*Time_Schedule!D{tr}"])
                    cell=lambda key:f'{columns[key]}{r}'
                    f={
                        'year':f'Time_Schedule!C{tr}','load':f'Time_Schedule!D{tr}',
                        'volume':f"{cell('load')}*{project['volume']}",
                        'revenue_eu':f"{cell('volume')}*{c['share_eu']}*{project['price_eu']}",
                        'revenue_asia':f"{cell('volume')}*{c['share_asia']}*{project['price_asia']}",
                        'outbound_cost':f"{cell('volume')}*{su_refs['outbound_unit']}",
                        'cbam_cost':f"{cell('volume')}*{su_refs['cbam_unit']}",
                        'revenue':f"{cell('revenue_eu')}+{cell('revenue_asia')}-{cell('outbound_cost')}-{cell('cbam_cost')}",
                        'raw_cost':f"{cell('volume')}*{c['raw_base']}",
                        'inbound_cost':f"{cell('volume')}*{su_refs['inbound_unit']}",
                        'duty_cost':f"{cell('volume')}*{su_refs['duty_unit']}",
                        'fixed_opex':f"{cell('load')}*{project['fixed_opex']}",
                        'opex':f"SUM({cell('raw_cost')}:{cell('fixed_opex')})",
                        'depreciation':f"{cap_refs['net']}/{project['years']}*{cell('load')}",
                        'ebit':f"{cell('revenue')}-{cell('opex')}-{cell('depreciation')}",
                        'holiday_rate':f'Taxation!D{tx}','tax_credit':f'Taxation!E{tx}',
                        'tax_gross':f"{cell('ebit')}*MIN({c['nominal_tax']},{cell('holiday_rate')})-{cell('tax_credit')}",
                        'literal_tax':f"MAX({cell('tax_gross')},{cell('ebit')}*{project['pillar_floor']})",
                        'cash_tax':f"MAX(0,{cell('literal_tax')})",
                        'operating_cf':f"{cell('ebit')}-{cell('cash_tax')}+{cell('depreciation')}",
                        'nwc_change':f'Time_Schedule!E{tr}',
                        'nwc_cash_effect':f"-{cell('nwc_change')}",
                        'investment':f"IF({cell('year')}=0,-{cap_refs['net']},0)",
                        'local_cf':f"{cell('investment')}+{cell('operating_cf')}+{cell('nwc_cash_effect')}",
                        'wht':f"MAX(0,{cell('operating_cf')})*{c['wht']}",
                        'parent_cf':f"{cell('local_cf')}-{cell('wht')}",
                        'parent_literal':f"IF({cell('local_cf')}<=0,{cell('local_cf')}-{cell('nwc_change')}*(1-{c['wht']}),{cell('local_cf')}-{cell('nwc_change')})",
                        'parent_literal_tax':f"{cell('investment')}+{cell('nwc_cash_effect')}+{cell('ebit')}-{cell('literal_tax')}+{cell('depreciation')}-MAX(0,{cell('ebit')}-{cell('literal_tax')}+{cell('depreciation')})*{c['wht']}",
                        'discount_factor':f"1/(1+{risk_refs['rate']})^{cell('year')}",
                        'discounted_parent':f"{cell('parent_cf')}*{cell('discount_factor')}",
                        'cumulative_parent':f"SUM({columns['discounted_parent']}$2:{cell('discounted_parent')})"}
                    cf.append(['='+f[key] for key in annual_fields])
                    for key in annual_fields:
                        self.bind(f'{name}!{cell(key)}',getattr(row,key),key,code,scenario,t,
                            unit='year' if key=='year' else 'fraction' if key in ('load','holiday_rate','discount_factor') else 'm2' if key=='volume' else 'USD',formula='CF_'+key.upper())
                    # Helpers supply independent discounted metrics for all flow definitions.
                    start=len(annual_fields)+1
                    for offset,key in enumerate(('local_cf','parent_literal','parent_literal_tax')):
                        cf.cell(r,start+offset,'='+cell(key)+'*'+cell('discount_factor'))
                        pc=col(start+offset); cc=col(start+3+offset)
                        cf.cell(r,start+3+offset,f'=SUM({pc}$2:{pc}{r})')
                    for offset,scope in enumerate(('parent','local','literal','literal_tax')):
                        pvcol=columns['discounted_parent'] if scope=='parent' else col(start+('local','literal','literal_tax').index(scope))
                        cumcol=columns['cumulative_parent'] if scope=='parent' else col(start+3+('local','literal','literal_tax').index(scope))
                        formula='="NOT_REACHED"' if r==2 else f'=IF(AND({cumcol}{r-1}<0,{cumcol}{r}>=-0.00000001,{pvcol}{r}>0),A{r}-1-{cumcol}{r-1}/{pvcol}{r},"NOT_REACHED")'
                        cf.cell(r,start+6+offset,formula)
                for scope in ('local','parent','literal','literal_tax'):
                    metric=getattr(result,scope); mr=metrics.max_row+1
                    flowkey={'local':'local_cf','parent':'parent_cf','literal':'parent_literal','literal_tax':'parent_literal_tax'}[scope]
                    flow=f"'{name}'!{columns[flowkey]}2:{columns[flowkey]}{n}"
                    pvcol=columns['discounted_parent'] if scope=='parent' else col(start+('local','literal','literal_tax').index(scope))
                    pv=f"'{name}'!{pvcol}2:{pvcol}{n}"
                    dppcol=col(start+6+('parent','local','literal','literal_tax').index(scope)); dpp=f"'{name}'!{dppcol}2:{dppcol}{n}"
                    metrics.append([scenario,code,scope,f'=SUM({pv})',f'=IFERROR(IRR({flow}),"NO_ROOT")',f'=IF(ISNUMBER(E{mr}),"UNIQUE","NO_ROOT")',
                        f'=IF(I{mr}>0,H{mr}/I{mr},"UNDEFINED")',f'=SUMIF({pv},">0",{pv})',f'=-SUMIF({pv},"<0",{pv})',
                        f'=IF(COUNT({dpp})>0,MIN({dpp}),"NOT_REACHED")',f'=IF(ISNUMBER(J{mr}),"REACHED","NOT_REACHED")'])
                    keys=('npv','irr','irr_status','pi','pv_inflows','pv_outflows','dpp','dpp_status')
                    for i,key in enumerate(keys,4):
                        expected=getattr(metric,key)
                        if expected is None: expected='NOT_REACHED' if key=='dpp' else 'NO_ROOT' if key=='irr' else 'UNDEFINED'
                        self.bind(f'Financial_Metrics!{col(i)}{mr}',expected,scope+'_'+key,code,scenario,
                            unit='fraction' if key=='irr' else 'year' if key=='dpp' else 'ratio' if key=='pi' else 'status' if 'status' in key else 'USD',formula='METRIC_'+key.upper())
                    metrics_refs[(scenario,code,scope)]=mr
        comp=sheet('Comparison',['country','E_ParentNPV_USD','variance_USD2','std_USD','P_negative','base_NPV_USD','literal_NPV_USD','literal_minus_economic_USD','literal_tax_minus_cash_USD'])
        for code,stat in scenarios.statistics.items():
            r=comp.max_row+1; values=[f"Financial_Metrics!D{metrics_refs[(s,code,'parent')]}" for s in 'ABC']
            probs=[sc_refs['p_'+s] for s in 'ABC']; base_m=metrics_refs[('B',code,'parent')]; lit_m=metrics_refs[('B',code,'literal')]; tax_m=metrics_refs[('B',code,'literal_tax')]
            comp.append([code,'='+'+'.join(p+'*'+v for p,v in zip(probs,values)),
                '='+'+'.join(f'{p}*({v}-B{r})^2' for p,v in zip(probs,values)),f'=SQRT(C{r})',
                '='+'+'.join(f'IF({v}<0,{p},0)' for p,v in zip(probs,values)),f'=Financial_Metrics!D{base_m}',f'=Financial_Metrics!D{lit_m}',f'=G{r}-F{r}',f'=Financial_Metrics!D{tax_m}-F{r}'])
            for i,key in enumerate(('expected','variance','std','probability_negative'),2):
                self.bind(f'Comparison!{col(i)}{r}',getattr(stat,key),key,code,'AGGREGATE',unit='USD2' if key=='variance' else 'fraction' if key=='probability_negative' else 'USD',formula='STAT_'+key.upper())
        assumptions=sheet('Assumptions',['assumption','decision'])
        for row in [('Payout','100% of positive operating cash; capital and NWC excluded'),('Tax losses','No cash refund, no loss carryforward without source data'),('Terminal value','TV=0; no disposal proceeds specified'),('PI','PV positive flows / absolute PV negative flows, including NWC'),('DPP','Calendar first recovery, linear interpolation within year'),('IRR','Full calendar IRR; baseline/scenario cashflows have one sign change'),('Model status','Educational source assumptions, not a statement of current tax law')]: assumptions.append(row)
        issues=sheet('Source_Issues',['id','page','issue','decision'])
        from ..services.documentation import SOURCE_ISSUES
        for issue in SOURCE_ISSUES: issues.append([issue[k] for k in ('id','page','issue','decision')])
        for ws in wb:
            ws.freeze_panes='C2'; ws.auto_filter.ref=ws.dimensions
            for cell in ws[1]: cell.font=Font(color='FFFFFF',bold=True); cell.fill=PatternFill('solid',fgColor='17365D')
            for cells in ws.iter_rows(min_row=2):
                for cell in cells:
                    if cell.data_type=='f': cell.font=Font(color='146342'); cell.number_format='#,##0.000000;[Red]-#,##0.000000'
                    elif isinstance(cell.value,(int,float)): cell.font=Font(color='1D4ED8'); cell.number_format='#,##0.000000'
            for column in ws.columns:
                letter=column[0].column_letter
                ws.column_dimensions[letter].width=min(48,max(15,len(str(column[0].value))+3))
        wb.calculation=CalcProperties(calcId=0,fullCalcOnLoad=True)
        wb.save(path)
        return self.refs

    def bind(self,ref,value,metric,code,scenario,year=None,unit='USD',formula=''):
        sheet,cell=ref.split('!'); self.refs.append(dict(sheet=sheet,cell=cell,python_value=value,metric_id=metric,country=code,scenario=scenario,year=year,unit=unit,formula_id=formula))

class ExcelGroundTruthService:
    def recalculate(self,path: Path,timeout: int):
        worker=Path(__file__).with_name('excel_worker.py')
        env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
        try:
            proc=subprocess.run([sys.executable,str(worker),str(path.resolve())],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,env=env)
            return ('PASS' if proc.returncode==0 and 'EXCEL_RECALCULATED' in proc.stdout else 'NOT_VERIFIED'),(proc.stdout+proc.stderr).strip()
        except subprocess.TimeoutExpired:
            return 'NOT_VERIFIED',f'Excel worker exceeded {timeout}s; no cache certification'
