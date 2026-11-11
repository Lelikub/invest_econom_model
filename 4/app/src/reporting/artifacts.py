from pathlib import Path
import json
from zipfile import ZipFile,ZIP_DEFLATED
from docx import Document
from openpyxl import load_workbook
from ..io_utils import sha256,write_json
from .word import REPORT_NAME

ARCHIVE_NAME='Практическая_4_ФИП_результаты.zip'

class ArtifactService:
    def validate(self,output,chart_count):
        required=['Ground_Truth.xlsx','HARNESS_LOG.xlsx',REPORT_NAME,'reconciliation.csv','results_summary.json','FINAL_REPORT.md']
        for name in required:
            p=output/name
            if not p.is_file() or p.stat().st_size==0: raise ValueError(f'Missing/empty artifact: {p}')
        wb=load_workbook(output/'Ground_Truth.xlsx',data_only=False)
        formulas=sum(c.data_type=='f' for w in wb for row in w for c in row); wb.close()
        if formulas<10000: raise ValueError('Missing independent spreadsheet formulas')
        doc=Document(output/REPORT_NAME)
        structure=json.loads((output/'report_structure.json').read_text(encoding='utf-8'))
        from .template import ReportTemplateLoader,TemplateReportValidationService
        _,titles,placeholders,template=ReportTemplateLoader().load(output.parent/'data/report_template.docx')
        if structure['template']['sha256']!=template['sha256']: raise ValueError('Report template fingerprint mismatch')
        template_check=TemplateReportValidationService().validate(doc,titles,placeholders,chart_count,structure['block_ids'],structure['block_ids'])
        with ZipFile(output/REPORT_NAME) as z:
            images=[n for n in z.namelist() if n.startswith('word/media/')]
            if len(images)!=chart_count: raise ValueError('DOCX image count mismatch')
            if z.testzip(): raise ValueError('Corrupt DOCX')
        return dict(status='PASS',formulas=formulas,embedded_figures=len(images),template_validation=template_check)

    def package(self,app,output):
        archive=output/ARCHIVE_NAME
        files=[]
        for path in sorted(app.rglob('*')):
            if not path.is_file(): continue
            rel=path.relative_to(app)
            if any(part in {'.venv','__pycache__','.pytest_cache','prior_outputs'} or part.startswith('test_tmp') for part in rel.parts): continue
            if path==archive or path.suffix=='.pyc' or path.name in ('package_manifest.json','run_manifest.json'): continue
            files.append(path)
        inventory=[dict(path=p.relative_to(app).as_posix(),bytes=p.stat().st_size,sha256=sha256(p)) for p in files]
        write_json(output/'package_manifest.json',dict(files=inventory,notes='Archive and run_manifest excluded from self-referential checksums'))
        files.extend([output/'package_manifest.json',output/'run_manifest.json'])
        with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as z:
            for p in files: z.write(p,p.relative_to(app).as_posix())
        with ZipFile(archive) as z:
            if z.testzip(): raise ValueError('ZIP CRC failed')
            import hashlib
            for row in inventory:
                if hashlib.sha256(z.read(row['path'])).hexdigest()!=row['sha256']: raise ValueError('ZIP SHA256 failed: '+row['path'])
        return dict(path=str(archive.relative_to(app)),sha256=sha256(archive),bytes=archive.stat().st_size,files=len(files),status='PASS')
