from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

import pymupdf
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation

from .documents import TECH,MEMO,SCRIPT
from .presentation import PPTX

ARCHIVE="Практическая_5_ФИП_результаты.zip"


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def json_to(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def verify_ooxml(path):
    with ZipFile(path) as archive:
        if archive.testzip() is not None or "[Content_Types].xml" not in archive.namelist():
            raise RuntimeError(f"OOXML container damaged: {path.name}")
        for name in archive.namelist():
            if name.endswith((".xml",".rels")):
                ET.fromstring(archive.read(name))


def audit_reports(folder,expected_sensitivity):
    audit={}
    for name,images,tables in ((TECH,10,11),(MEMO,3,3),(SCRIPT,0,0)):
        path=folder/name
        verify_ooxml(path)
        doc=Document(path)
        if len(doc.inline_shapes)!=images or len(doc.tables)!=tables or not doc.paragraphs:
            raise RuntimeError(f"Unexpected table or figure count: {name}")
        tags=[]
        for el in doc.element.body:
            if el.tag.endswith("}tbl"):
                tags.append("table")
            elif el.tag.endswith("}p"):
                has_image=any(child.tag.endswith("}drawing") for child in el.iter())
                has_text=any(child.tag.endswith("}t") and child.text for child in el.iter())
                tags.append("image" if has_image else "text" if has_text else "empty")
        analytical_tables=[i for i,t in enumerate(tags) if t=="table"][:images]
        for i in analytical_tables:
            if tags[i+1:i+4]!=["image","text","text"]:
                raise RuntimeError(f"Analytical order table → chart → caption → text failed: {name}")
        audit[name]={"status":"PASS","tables":tables,"images":images,"sha256":sha(path)}
    path=folder/PPTX
    verify_ooxml(path)
    prs=Presentation(path)
    if len(prs.slides)!=5 or abs(prs.slide_width/prs.slide_height-16/9)>.0001:
        raise RuntimeError("Presentation must have five slides in 16:9")
    for i,slide in enumerate(prs.slides,1):
        if not any(shape.has_text_frame and shape.text for shape in slide.shapes):
            raise RuntimeError(f"Empty slide {i}")
        if any(s.left<0 or s.top<0 or s.left+s.width>prs.slide_width+300 or s.top+s.height>prs.slide_height+300
               for s in slide.shapes):
            raise RuntimeError(f"Element outside slide {i}")
    audit[PPTX]={"status":"PASS","slides":5,"aspect_ratio":"16:9","sha256":sha(path)}
    for name in ("Ground_Truth.xlsx","HARNESS_LOG.xlsx"):
        path=folder/name
        verify_ooxml(path)
        wb=load_workbook(path,read_only=True)
        try:
            if any(ws.max_row<2 for ws in wb):
                raise RuntimeError(f"Empty worksheet: {name}")
            formulas=sum(cell.data_type=="f" for ws in wb for row in ws.iter_rows() for cell in row)
            if name.startswith("Ground"):
                if formulas<200 or not set(expected_sensitivity)<=set(wb.sheetnames):
                    raise RuntimeError(f"Expected Excel formulas or Sensitivity Report are missing: {name}")
            audit[name]={"status":"PASS","sheets":wb.sheetnames,"formulas":formulas,"sha256":sha(path)}
        finally:
            wb.close()
    return audit


def render_office(folder,logs,review_path,enabled):
    worker=Path(__file__).with_name("office_worker.py")
    if not enabled:
        return {"status":"EDITOR_NOT_VERIFIED","cause":"Skipped by CLI option"}
    try:
        r=subprocess.run([sys.executable,str(worker),"documents",str(folder)],cwd=logs,capture_output=True,
                         encoding="utf-8",errors="replace",timeout=120)
        (logs/"editors.log").write_text(r.stdout+r.stderr,encoding="utf-8")
        data=json.loads(r.stdout) if not r.returncode else {"status":"EDITOR_NOT_VERIFIED","cause":"See logs/editors.log"}
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        (logs/"editors.log").write_text(str(error),encoding="utf-8")
        return {"status":"EDITOR_NOT_VERIFIED","cause":type(error).__name__}
    if data.get("status")=="OPENED_AND_RENDERED":
        reviews=json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else {}
        rendered={}
        for name,pages in data["page_counts"].items():
            file=folder/"editor_previews"/(Path(name).stem+".pdf")
            with pymupdf.open(file) as doc:
                if len(doc)!=pages or any(not page.get_text().strip() for page in doc):
                    raise RuntimeError(f"Incomplete Office rendering for {name}")
                layout_signature=sha256()
                for page in doc:
                    layout_signature.update(page.get_pixmap(matrix=pymupdf.Matrix(.6,.6),alpha=False).samples)
                digest=layout_signature.hexdigest()
            review=reviews.get(name,{})
            visual=review.get("signature")==digest and review.get("status")=="PASS" and bool(review.get("reviewer"))
            rendered[name]=dict(page_count=pages,visual="PASS" if visual else "VISUAL_NOT_VERIFIED",signature=digest,
                                conclusion=review.get("conclusion","") if visual else "")
        data["rendered"]=rendered
    return data


def package(app,output,logs,manifest_path):
    out_files=[p for p in output.rglob("*") if p.is_file() and p.name not in {ARCHIVE,"package_manifest.json"}]
    app_files=[app/"main.py",app/"requirements.txt",app/"README.md"]
    for folder in ("src","tests","data","docs"):
        app_files.extend(p for p in (app/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    log_names=("execution.log","events.jsonl","tests.log","excel_base.log","excel.log","editors.log",
               "cbc_lp.log","cbc_milp.log","cbc_fixed.log","cbc_portfolio.log","development_red.log")
    log_files=[logs/name for name in log_names if (logs/name).is_file()]
    items={**{p.relative_to(app).as_posix():p for p in app_files},
           **{f"logs/{p.name}":p for p in log_files},
           **{f"output/{p.relative_to(output).as_posix()}":p for p in out_files},
           "run_manifest.json":manifest_path}
    provenance={name:{"sha256":sha(path),"bytes":path.stat().st_size} for name,path in sorted(items.items())}
    listing=output/"package_manifest.json"
    json_to(listing,{"files":provenance})
    archive=output/ARCHIVE
    with ZipFile(archive,"w",compression=ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in items.items():
            z.write(path,name)
        z.write(listing,"output/package_manifest.json")
    with ZipFile(archive) as z:
        if z.testzip() is not None or set(z.namelist())!=set(items)|{"output/package_manifest.json"}:
            raise RuntimeError("ZIP checksum or member list is invalid")
        for name,info in provenance.items():
            if sha256(z.read(name)).hexdigest()!=info["sha256"]:
                raise RuntimeError(f"ZIP member SHA-256 mismatch: {name}")
    return dict(name=archive.name,sha256=sha(archive),bytes=archive.stat().st_size,members=len(items)+1)
