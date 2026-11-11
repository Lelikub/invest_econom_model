"""Bounded Word/PDF rendering for checking the final document's physical layout."""
from pathlib import Path
import os
import subprocess
import sys
import pymupdf
from ..io_utils import sha256,write_json

class WordPreviewService:
    def render(self,docx_path,timeout=90):
        folder=Path(docx_path).parent/'internal_review'; folder.mkdir(exist_ok=True)
        pdf=folder/'report.pdf'; before=sha256(docx_path)
        env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
        try:
            process=subprocess.run([sys.executable,str(Path(__file__).with_name('word_worker.py')),str(docx_path.resolve()),str(pdf.resolve())],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,env=env)
            detail=(process.stdout+process.stderr).strip()
            if process.returncode!=0 or 'WORD_PDF_RENDERED' not in process.stdout or not pdf.exists():
                result=dict(status='NOT_VERIFIED',detail=detail,purpose='Optional physical layout preview; DOCX structural audit is separate')
            else:
                with pymupdf.open(pdf) as document:
                    if not len(document): raise ValueError('Empty report PDF')
                    for i in (0,min(1,len(document)-1),min(6,len(document)-1)):
                        document[i].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(folder/f'page_{i+1:03d}.png')
                    result=dict(status='PASS',detail=detail,pages=len(document),pdf=str(pdf.relative_to(Path(docx_path).parent)),
                        sha256=sha256(pdf),docx_sha256=before,visual_status='VISUAL_NOT_VERIFIED')
        except subprocess.TimeoutExpired:
            result=dict(status='NOT_VERIFIED',detail=f'Word rendering timed out after {timeout}s')
        if sha256(docx_path)!=before: raise ValueError('Preview worker changed the source DOCX')
        write_json(folder/'render_status.json',result)
        return result
