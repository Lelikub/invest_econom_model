"""Independent spreadsheet formulas and honest cached-value reconciliation."""
from dataclasses import asdict
from pathlib import Path
import math
import subprocess
import sys
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment,Font,PatternFill
from openpyxl.workbook.properties import CalcProperties


def style_book(wb):
    for ws in wb:
        ws.freeze_panes='B2'
        ws.auto_filter.ref=ws.dimensions
        for cell in ws[1]:
            cell.font=Font(bold=True,color='FFFFFF')
            cell.fill=PatternFill('solid',fgColor='17365D')
        for col in ws.columns:
            letter=col[0].column_letter
            ws.column_dimensions[letter].width=34 if letter=='A' else 24
        for row in ws:
            for cell in row:
                cell.alignment=Alignment(vertical='top',wrap_text=True)
                if isinstance(cell.value,float): cell.number_format='0.0000000000'


class ExcelGroundTruthWriter:
    def write(self,path,p,m,s,base,stress,returns,audit,tests,waterfalls,source_rows=()):
        wb=Workbook(); ws=wb.active; ws.title='Inputs'
        ws.append(['parameter','value','unit','source','raw_value','source_page'])
        provenance={row['parameter_code']:row for row in source_rows}
        x={}
        for group,dto in [('project',p),('market',m),('shock',s)]:
            for k,v in asdict(dto).items():
                source=provenance.get(k,{})
                ws.append([k,v,source.get('unit','text' if isinstance(v,str) else 'See parsed CSV'),
                    source.get('source_file',f'{group}_parameters.csv' if k!='currency' else 'PDF 1–2: USD financing'),
                    source.get('raw_value',''),source.get('source_page','')])
                x[k]=f"'Inputs'!B{ws.max_row}"
        refs={}; base_refs={}; stress_refs={}
        def sheet(title,items,scenario,local):
            sh=wb.create_sheet(title); sh.append(['metric_id','independent Excel formula','Python (comparison only)','source'])
            result=base.metrics if scenario=='base' else stress.metrics
            for key,formula,source in items:
                row=sh.max_row+1
                sh.append([key,'='+formula,result.get(key),source])
                local[key]=f"'{title}'!B{row}"; refs[f'{scenario}.{key}']=local[key]
            return sh
        b=base_refs
        # Sequential generation ensures every formula references only prior cells.
        sh=sheet('Base',[], 'base',b)
        def add(sh,local,scenario,key,formula,source):
            row=sh.max_row+1
            result=base.metrics if scenario=='base' else stress.metrics
            sh.append([key,'='+formula,result[key],source])
            local[key]=f"'{sh.title}'!B{row}"; refs[f'{scenario}.{key}']=local[key]
        def B(key,formula,source='PDF 5–6 / lecture 5'):
            add(sh,b,'base',key,formula,source)
        B('t_eff',f"MAX({x['t_nominal']}-{x['rd_relief']},{x['t_floor']})")
        B('de_peer',f"{x['debt_peer']}/{x['equity_peer']}")
        B('beta_u',f"{x['beta_peer']}/(1+(1-{x['tax_peer']})*{b['de_peer']})")
        B('de',f"{x['wd']}/{x['we']}")
        B('beta_l',f"{b['beta_u']}*(1+(1-{b['t_eff']})*{b['de']})")
        for key in ('rf','erp','crp','we','wd'): B(key,x[key])
        B('ke',f"{b['rf']}+{b['beta_l']}*{b['erp']}+{b['crp']}")
        B('kd',f"{b['rf']}+{x['s_base']}")
        B('kd_after_tax',f"{b['kd']}*(1-{b['t_eff']})")
        B('wacc',f"{b['we']}*{b['ke']}+{b['wd']}*{b['kd_after_tax']}")
        B('dscr',x['dscr0'])
        B('equity',f"{x['capex']}*{x['we']}")
        B('debt',f"{x['capex']}*{x['wd']}")
        B('ebitda',f"{x['revenue']}-{x['opex']}")
        for key,value in [('credit_spread','0'),('delta_total','0'),('pi_exp','0'),('beta_multiplier','1')]: B(key,value)
        t=stress_refs; sh=sheet('Stress',[],'stress',t)
        def S(key,formula): add(sh,t,'stress',key,formula,'PDF 8–10 / lecture 27–30')
        S('t_eff',b['t_eff']); S('de_peer',b['de_peer'])
        S('pi_exp',f"{x['eta']}*{x['oil']}")
        S('rf',f"{x['rf']}+{t['pi_exp']}+{x['term_premium']}+{x['alpha_cross']}*{x['taiwan']}")
        S('beta_multiplier',f"1+{x['psi_tariff']}*{x['tariff']}+{x['psi_energy']}*{x['oil']}+{x['psi_cross']}*{x['tariff']}*{x['oil']}+{x['psi_tw']}*{x['taiwan']}")
        S('beta_u',f"{b['beta_u']}*{t['beta_multiplier']}")
        S('delta_total',f"{x['crash']}+{x['flight']}")
        S('equity',f"{b['equity']}*(1-{t['delta_total']})"); S('debt',b['debt'])
        S('de',f"{t['debt']}/{t['equity']}")
        S('we',f"{t['equity']}/({t['equity']}+{t['debt']})")
        S('wd',f"{t['debt']}/({t['equity']}+{t['debt']})")
        S('beta_l',f"{t['beta_u']}*(1+(1-{t['t_eff']})*{t['de']})")
        S('erp',f"{x['erp']}+{x['panic_lambda']}*{x['crash']}")
        S('crp',f"{x['crp']}+{x['crp_europe']}+{x['taiwan']}")
        S('ke',f"{t['rf']}+{t['beta_l']}*{t['erp']}+{t['crp']}")
        S('dscr',f"{x['dscr0']}*(1-{x['mu_ebitda']})")
        S('credit_spread',f'IF({t["dscr"]}>={x["covenant"]},0,IF({t["dscr"]}>=1,{x["gamma1"]}*({x["covenant"]}/{t["dscr"]}-1),NA()))')
        S('kd',f"{t['rf']}+{x['s_base']}+{x['spread_europe']}+{t['credit_spread']}")
        S('kd_after_tax',f"{t['kd']}*(1-{t['t_eff']})")
        S('wacc',f"{t['we']}*{t['ke']}+{t['wd']}*{t['kd_after_tax']}")
        S('ebitda',f"{x['ebitda']}*(1-{x['mu_ebitda']})")
        ass=wb.create_sheet('Illustrative_Assumptions')
        ass.append(['assumption','value','status'])
        for row in [('cash_taxes',0,'ILLUSTRATIVE ONLY; tax base unknown'),('delta_nwc',0,'ILLUSTRATIVE ONLY'),
                    ('revenue',f"={x['revenue']}",'Fixed revenue illustration'),('opex',f"=B4-{t['ebitda']}",'Residual OPEX, not measured')]: ass.append(row)
        wf=wb.create_sheet('Waterfall'); wf.append(['metric_id','consistent','literal_pdf','source'])
        wf_rows=[('dividend_lockup',f"{t['dscr']}<{x['covenant']}",f"B2",'PDF 10'),
            ('debt_service',x['debt_service'],x['debt_service'],'Contractual amount unchanged'),
            ('cfads_before_debt_service',f"{t['ebitda']}-'Illustrative_Assumptions'!B2-'Illustrative_Assumptions'!B3",'B4','ILLUSTRATIVE cash taxes/NWC=0'),
            ('debt_paid','MIN(MAX(B4,0),B3)','IF(C2,0,MIN(MAX(C4,0),C3))','PDF conflict separated'),
            ('cash_after_debt_service','B4-B5','C4-C5','Cash after debt'),
            ('dsra','IF(B2,MAX(B6,0),0)','IF(C2,MAX(C6,0),0)','Illustrative allocation of available surplus'),
            ('dividends','IF(B2,0,MAX(B6-B7,0))','IF(C2,0,MAX(C6-C7,0))','Lockup'),
            ('retained','B6-B7-B8','C6-C7-C8','Balance'),
            ('shortfall','MAX(B3-B5,0)','MAX(C3-C5,0)','Unpaid contractual amount')]
        for i,(key,consistent,literal,source) in enumerate(wf_rows,2):
            wf.append([key,'='+consistent,'='+literal,source])
            refs[f'waterfall.{key}']=f"'Waterfall'!B{i}"
            refs[f'literal.{key}']=f"'Waterfall'!C{i}"
        mo=wb.create_sheet('Monthly_Returns'); mo.append(['Date','HXL','GSPC'])
        if hasattr(returns,'iterrows'):
            for date,row in returns.iterrows(): mo.append([str(date.date()),float(row['HXL']),float(row['^GSPC'])])
            n=mo.max_row
            ol=wb.create_sheet('OLS'); ol.append(['metric_id','formula'])
            for key,formula in [('beta_ols',f'SLOPE(Monthly_Returns!B2:B{n},Monthly_Returns!C2:C{n})'),
                ('alpha_raw',f'INTERCEPT(Monthly_Returns!B2:B{n},Monthly_Returns!C2:C{n})'),
                ('r_squared',f'RSQ(Monthly_Returns!B2:B{n},Monthly_Returns!C2:C{n})')]:
                ol.append([key,'='+formula]); refs[f'ols.{key}']=f"'OLS'!B{ol.max_row}"
        disc=wb.create_sheet('Discount'); disc.append(['year','base_factor','stress_factor','unit'])
        for year in range(1,11):
            row=year+1; disc.append([year,f'=1/(1+{b["wacc"]})^A{row}',f'=1/(1+{t["wacc"]})^A{row}','PV of one USD at year t'])
            refs[f'discount_base.year_{year}']=f"'Discount'!B{row}"
            refs[f'discount_stress.year_{year}']=f"'Discount'!C{row}"
        checks=wb.create_sheet('Checks'); checks.append(['check','formula','expected'])
        for key,formula,expected in [('base_weights',f"{b['we']}+{b['wd']}",1),('stress_weights',f"{t['we']}+{t['wd']}",1),
            ('delta_valid',f"{t['delta_total']}<1",True),('ebitda',f"{x['revenue']}-{x['opex']}-{x['ebitda']}",0),
            ('waterfall_balance','Waterfall!B4-Waterfall!B5-Waterfall!B7-Waterfall!B8-Waterfall!B9',0)]:
            checks.append([key,'='+formula,expected])
            refs[f'checks.{key}']=f"'Checks'!B{checks.max_row}"
        dec=wb.create_sheet('Decomposition'); dec.append(['component','formula'])
        for key,formula in [('Ke',f"{b['we']}*({t['ke']}-{b['ke']})"),('Kd_net',f"{b['wd']}*({t['kd_after_tax']}-{b['kd_after_tax']})"),
            ('weights',f"({t['we']}-{b['we']})*{t['ke']}+({t['wd']}-{b['wd']})*{t['kd_after_tax']}")]:
            dec.append([key,'='+formula])
            refs[f'decomposition.{key}']=f"'Decomposition'!B{dec.max_row}"
        for title,rows in [('Data_Audit',audit),('Tests',tests)]:
            tab=wb.create_sheet(title)
            if rows:
                tab.append(list(rows[0])); [tab.append([str(v) if isinstance(v,(dict,list)) else v for v in row.values()]) for row in rows]
            else: tab.append(['status']); tab.append(['No records supplied'])
        verify=wb.create_sheet('Verification'); verify.append(['metric_id','Excel value','Python value','difference','status'])
        for key,ref in refs.items():
            scenario,metric=key.split('.')
            obj=base.metrics if scenario=='base' else stress.metrics if scenario=='stress' else None
            if obj is None: continue
            row=verify.max_row+1
            verify.append([key,'='+ref,obj[metric],f'=ABS(B{row}-C{row})',f'=IF(D{row}<=1E-10+1E-8*ABS(C{row}),"PASS","FAIL")'])
        wb.calculation=CalcProperties(calcMode='auto',fullCalcOnLoad=True,forceFullCalc=True)
        style_book(wb); path.parent.mkdir(parents=True,exist_ok=True); wb.save(path)
        return refs


class ExcelService:
    def __init__(self,timeout=90): self.timeout=timeout

    def recalculate(self,path):
        if not path.is_file(): return 'NOT_VERIFIED','Workbook missing'
        worker=Path(__file__).with_name('excel_worker.py')
        try:
            result=subprocess.run([sys.executable,str(worker),str(path.resolve())],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=self.timeout)
        except (subprocess.TimeoutExpired,OSError) as exc:
            return 'NOT_VERIFIED',str(exc)
        if result.returncode or 'EXCEL_RECALCULATED' not in result.stdout:
            return 'NOT_VERIFIED',(result.stderr or result.stdout)[-4000:]
        return 'PASS',result.stdout.strip()


class ComparisonService:
    @staticmethod
    def reconcile(path,refs,base,stress,engine_verified,regression=None,waterfalls=(),lookup_extra=None):
        wb=load_workbook(path,data_only=True,read_only=True); rows=[]
        lookup={'base':base.metrics,'stress':stress.metrics}
        if regression is not None: lookup['ols']=asdict(regression)
        for name,obj in zip(('waterfall','literal'),waterfalls): lookup[name]=asdict(obj)
        if lookup_extra: lookup.update(lookup_extra)
        for key,ref in refs.items():
            scenario,metric=key.split('.')
            if scenario not in lookup: continue
            py=lookup[scenario][metric]
            sheet,cell=ref.split('!'); excel=wb[sheet.strip("'")][cell].value
            valid=engine_verified and isinstance(excel,(int,float,bool)) and math.isfinite(excel)
            diff=abs(py-excel) if valid else None
            status=('PASS' if math.isclose(py,excel,rel_tol=1e-8,abs_tol=1e-10) else 'FAIL') if valid else 'NOT_VERIFIED'
            rows.append(dict(metric_id=metric,scenario=scenario,python_value=py,excel_value=excel if valid else None,
                analytical_expected=None,abs_diff=diff,relative_diff=diff/abs(py) if valid and py!=0 else None,
                tolerance='rtol=1e-8; atol=1e-10',verification_status=status,source_ref=ref,note='Independent spreadsheet formula'))
        wb.close(); return rows
