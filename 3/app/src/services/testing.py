from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from ..models import TestResult
from ..calculators.finance import CAPMCalculator,HamadaBetaCalculator,CostOfDebtCalculator,WACCCalculator
from dataclasses import asdict
from ..io_utils import write_csv


class TestService:
    def run(self,app_dir,tables,logger):
        xml=app_dir/'logs'/f'tests_{logger.run_id}.xml'
        proc=subprocess.run([sys.executable,'-m','pytest',str(app_dir/'tests'),'-q',f'--junitxml={xml}',
                             f'--basetemp={app_dir / "logs" / ("test_tmp_"+logger.run_id)}',
                             '-p','no:cacheprovider'],cwd=app_dir,capture_output=True,text=True,
                             encoding='utf-8',errors='replace',timeout=180)
        transcript=proc.stdout+'\n'+proc.stderr
        (app_dir/'logs'/f'tests_{logger.run_id}.log').write_text(transcript,encoding='utf-8')
        with (app_dir/'logs/tests.log').open('a',encoding='utf-8') as stream: stream.write(logger.run_id+'\n'+transcript)
        rows=[]
        if xml.exists():
            root=ET.parse(xml).getroot()
            for case in root.iter('testcase'):
                failure=case.find('failure'); error=case.find('error'); skipped=case.find('skipped')
                node=failure if failure is not None else error
                rows.append(dict(test_id=case.attrib.get('classname','')+'.'+case.attrib['name'],
                    inputs='See test source; controlled inputs',expected='Assertions pass',
                    actual='PASS' if node is None and skipped is None else 'FAIL' if node is not None else 'SKIPPED',
                    tolerance='case-specific',passed=node is None and skipped is None,
                    exception=node.text if node is not None else '',source='tests/'+case.attrib.get('classname','')))
        edges=[TestResult('edge_beta_zero','rf=.041,beta=0,erp=.05,crp=.012','.053',
                    str(CAPMCalculator.calculate(.041,0,.05,.012)),1e-12,abs(CAPMCalculator.calculate(.041,0,.05,.012)-.053)<1e-12,source='PDF 7'),
            TestResult('edge_all_equity','betaU=1.2,t=.15,de=0,we=1,wd=0','betaL=1.2,WACC=.12',
                f'betaL={HamadaBetaCalculator.relever(1.2,.15,0)},WACC={WACCCalculator.calculate(1,0,.12,.05)}',
                1e-12,HamadaBetaCalculator.relever(1.2,.15,0)==1.2 and WACCCalculator.calculate(1,0,.12,.05)==.12,source='PDF 7'),
            TestResult('edge_tax_zero','kd=.0585,t=0 (isolated model, floor not applied)','.0585',
                str(CostOfDebtCalculator.after_tax(.0585,0)),1e-12,CostOfDebtCalculator.after_tax(.0585,0)==.0585,source='PDF 7')]
        rows.extend(asdict(r) for r in edges)
        write_csv(tables/'test_results.csv',rows)
        logger.log('tests',transcript[-2000:])
        if proc.returncode or not rows or not all(r['passed'] for r in rows):
            logger.issue('test_failure','tests','Автоматическая верификация','pytest',transcript[-4000:],
                'См. traceback','Расчёты не подтверждены','FAILED','implementation error')
            raise ValueError('Automated tests failed; see logs/tests.log')
        latest={event['issue_id']:event for event in logger.history()}
        for key in ('test_failure','exception_tests'):
            if key in latest:
                old=latest[key]
                logger.issue(key,'tests',old['task'],old['code'],old['issue'],old['cause'],
                    'После исправлений повторно выполнен весь набор тестов',f'RESOLVED: PASS {len(rows)}/{len(rows)}',old['category'])
        return rows
