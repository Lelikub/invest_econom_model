import json
import logging
import uuid
from pathlib import Path
from ..io_utils import now

class LoggingService:
    def __init__(self,app: Path):
        self.run_id=now()[:19].replace(':','').replace('-','').replace('T','_')+'_'+uuid.uuid4().hex[:8]
        self.directory=app/'logs'; self.directory.mkdir(parents=True,exist_ok=True); self.issues=[]
        for name in ('pipeline','calculations','tests','errors'): (self.directory/(name+'.log')).touch(exist_ok=True)

    def event(self,stage,message,status='INFO',kind='pipeline',**details):
        row=dict(timestamp=now(),run_id=self.run_id,stage=stage,status=status,message=message,**details)
        with (self.directory/'events.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
        with (self.directory/(kind+'.log')).open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')

    def issue(self,kind,id,stage,observed,decision,status='WARNING',**details):
        row=dict(id=id,kind=kind,date=now(),run_id=self.run_id,stage=stage,observed=observed,decision=decision,status=status,**details)
        self.issues.append(row); self.event(stage,observed,status,kind='errors',issue_id=id,decision=decision,**details)
