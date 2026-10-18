from pathlib import Path
import csv
import hashlib
import json


def sha256(path: Path) -> str:
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def write_csv(path: Path, rows: list[dict], fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fields:
        raise ValueError(f'No schema for empty table: {path.name}')
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding='utf-8')
