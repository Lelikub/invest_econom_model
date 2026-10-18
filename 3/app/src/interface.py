from pathlib import Path
import argparse
import json
from .models import PipelineConfig
from .controller import PipelineController


class ApplicationInterface:
    def run(self,argv=None):
        app=Path(__file__).resolve().parents[1]
        parser=argparse.ArgumentParser(description='AeroCarbon Synth: PDF → CSV → WACC/OLS/Excel/Word/ZIP')
        parser.add_argument('--pdf',type=Path,default=app.parent/'data/Задание_к_практическому_занятию_3_ФИП.pdf')
        parser.add_argument('--prices',type=Path,default=app.parent/'data/hxl_gspc_adj_close_5y.csv')
        parser.add_argument('--lecture',type=Path,default=app.parents[1]/'lectuion/Лекция 5 ФИП слайды.pdf')
        parser.add_argument('--output',type=Path,default=app/'output')
        parser.add_argument('--excel-timeout',type=int,default=90)
        args=parser.parse_args(argv)
        result=PipelineController(PipelineConfig(app,args.pdf,args.prices,args.lecture,args.output,args.excel_timeout)).run()
        print(json.dumps({'status':result['status'],'stages':result.get('stages',{}),'error':result.get('error'),
            'output':str(args.output)},ensure_ascii=False,indent=2))
        return 1 if result['status']=='FAILED' else 2 if result['status']=='NOT_VERIFIED' else 0
