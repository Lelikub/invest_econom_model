import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from ..io_utils import write_csv

class TestService:
    def run(self,app,logger):
        xml=app/'logs'/f'tests_{logger.run_id}.xml'
        env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'; env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
        cmd=[sys.executable,'-m','pytest',str(app/'tests'),'-q','-p','no:cacheprovider',f'--basetemp={app/"logs"/("test_tmp_"+logger.run_id)}',f'--junitxml={xml}']
        proc=subprocess.run(cmd,cwd=app,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=240)
        text=proc.stdout+proc.stderr
        (app/'logs'/f'tests_{logger.run_id}.log').write_text(text,encoding='utf-8')
        with (app/'logs/tests.log').open('a',encoding='utf-8') as f: f.write('\n'+logger.run_id+'\n'+text)
        rows=[]
        if xml.exists():
            for t in ET.parse(xml).iter('testcase'):
                status='FAIL' if t.find('failure') is not None or t.find('error') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
                rows.append(dict(test_id=t.get('classname','')+'::'+t.get('name',''),status=status,seconds=float(t.get('time','0')),details=''.join(t.itertext()).strip()))
        write_csv(app/'output/tables/test_results.csv',rows)
        if proc.returncode!=0:
            logger.issue('CODE_ERROR','TEST_FAILURE','09',text[-12000:],'Tests must pass before completion','FAIL')
            raise RuntimeError(f'pytest failed ({proc.returncode}); see {xml.with_suffix(".log")}')
        logger.event('09',f'{len(rows)} tests passed','PASS',kind='tests')
        return rows
