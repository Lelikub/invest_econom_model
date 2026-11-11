from pathlib import Path
import csv
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def now() -> str:
    return datetime.now(ZoneInfo('Europe/Moscow')).isoformat()

def write_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,default=str),encoding='utf-8')

def write_csv(path, rows, fields=None):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); rows=list(rows)
    fields=fields or (list(dict.fromkeys(key for row in rows for key in row)) if rows else ['status'])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='raise'); writer.writeheader(); writer.writerows(rows)

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
