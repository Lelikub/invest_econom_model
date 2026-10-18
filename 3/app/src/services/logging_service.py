"""Append-only operational logs and observed issue history."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import logging
import uuid
from ..models import HarnessEntry


class LoggingService:
    def __init__(self,app_dir):
        self.root=app_dir/'logs'; self.root.mkdir(parents=True,exist_ok=True)
        self.run_id=datetime.now(ZoneInfo('Europe/Moscow')).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
        self.logger=logging.getLogger(self.run_id); self.logger.setLevel(logging.INFO)
        fmt=logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        for handler in (logging.StreamHandler(),logging.FileHandler(self.root/'pipeline.log',encoding='utf-8')):
            handler.setFormatter(fmt); self.logger.addHandler(handler)
        self.events=self.root/'events.jsonl'

    def log(self,step,message):
        line=f'run={self.run_id} step={step} {message}'
        self.logger.info(line)
        if step in ('data_validation','chart_validation','tests'):
            with (self.root/f'{step}.log').open('a',encoding='utf-8') as stream:
                stream.write(datetime.now(ZoneInfo('Europe/Moscow')).isoformat()+' '+line+'\n')

    def issue(self,issue_id,stage,task,code,issue,cause,resolution,recheck,category):
        entry=HarnessEntry(issue_id,stage,task,code,issue,cause,resolution,recheck,category,
            self.run_id,datetime.now(ZoneInfo('Europe/Moscow')).isoformat())
        with self.events.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(asdict(entry),ensure_ascii=False)+'\n')
        self.logger.warning('%s: %s; %s',issue_id,issue,resolution)

    def exception(self,step,exc):
        import traceback
        detail=traceback.format_exc()
        with (self.root/'errors.log').open('a',encoding='utf-8') as stream:
            stream.write(f'{self.run_id} {step}\n{detail}\n')
        self.issue('exception_'+step,step,'Завершить шаг с диагностикой','',str(exc),detail,
            'Сохранена диагностика; итог FAILED','FAILED','implementation error')

    def history(self):
        if not self.events.exists(): return []
        return [json.loads(line) for line in self.events.read_text(encoding='utf-8').splitlines() if line.strip()]
