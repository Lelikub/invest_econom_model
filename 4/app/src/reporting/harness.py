from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill
from ..io_utils import write_csv

class HarnessLogWriter:
    def write(self,path,manifest,issues,tests=(),reconciliation=()):
        wb=Workbook(); wb.remove(wb.active)
        def add(name,rows,default_fields):
            rows=list(rows); fields=list(dict.fromkeys(k for r in rows for k in r)) or default_fields
            ws=wb.create_sheet(name); ws.append(fields)
            for row in rows:
                ws.append([str(row.get(k,''))[:32000] if isinstance(row.get(k),(dict,list,tuple)) else row.get(k,'') for k in fields])
            ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
            for c in ws[1]: c.font=Font(bold=True,color='FFFFFF'); c.fill=PatternFill('solid',fgColor='17365D')
            for cells in ws.columns: ws.column_dimensions[cells[0].column_letter].width=min(65,max(16,len(str(cells[0].value))+3))
        add('Summary',[dict(stage=k,**v) for k,v in manifest.get('stages',{}).items()],['stage','status'])
        add('Errors',[r for r in issues if r['kind'] in ('CODE_ERROR','ENVIRONMENT','VERIFICATION_LIMIT')],['id','kind','observed','decision','status'])
        add('Source_Issues',[r for r in issues if r['kind']=='SOURCE_ISSUE'],['id','observed','decision'])
        add('Tests',tests,['test_id','status'])
        add('Reconciliation',reconciliation,['metric_id','status'])
        add('Fixes',[r for r in issues if r['kind']=='CODE_ERROR'],['id','observed','decision','retest'])
        add('Assumptions',[
            dict(id='PAYOUT',assumption='100% positive operating CF distributed, no WHT on capital/NWC'),
            dict(id='NO_REFUND',assumption='Cash tax nonnegative, no unprovided loss carryforward'),
            dict(id='TV_ZERO',assumption='No terminal value specified, TV=0'),
            dict(id='CALENDAR',assumption='Full discrete calendar with VNM half years'),
            dict(id='PI',assumption='PV positive flows / |PV negative flows| including NWC')],['id','assumption'])
        add('AI_Hallucination_Risks',[
            dict(risk='Invented numerical results',control='All reported numbers bound to executed calculators / exported CSV'),
            dict(risk='Python reused as Excel truth',control='Independent formulas; actual Excel COM cache only'),
            dict(risk='Fabricated visual review',control='SHA256-bound review; absent review is VISUAL_NOT_VERIFIED'),
            dict(risk='Fabricated code defects',control='Observed assertion / traceback only; source issues classified separately'),
            dict(risk='Outdated legal assertion',control='Educational PDF assumptions; no claim about current tax law')],['risk','control'])
        wb.save(path)
        write_csv(path.with_suffix('.csv'),issues or [dict(status=manifest.get('status','RUNNING'))])
