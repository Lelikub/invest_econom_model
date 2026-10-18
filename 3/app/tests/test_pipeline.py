from pathlib import Path
import json
import pytest
from src.controller import PipelineController
from src.models import PipelineConfig
from src.reporting.report import ArtifactValidationService


def test_pipeline_missing_pdf_preserves_failed_manifest(tmp_path):
    app=tmp_path/'app'; app.mkdir()
    cfg=PipelineConfig(app,tmp_path/'missing.pdf',tmp_path/'missing.csv',tmp_path/'lecture.pdf',app/'output',3)
    result=PipelineController(cfg).run()
    assert result['status']=='FAILED'
    assert (cfg.output/'HARNESS_LOG.xlsx').is_file()
    assert json.loads((app/'run_manifest.json').read_text(encoding='utf-8'))['status']=='FAILED'
    assert not (cfg.output/'Итоговый_отчет_ФИП_Практическая_3.docx').exists()

def test_corrupt_artifacts_are_rejected(tmp_path):
    with pytest.raises((ValueError,FileNotFoundError)):
        ArtifactValidationService.verify(tmp_path,[])


def test_testservice_keeps_temporary_files_within_application(tmp_path):
    from src.services.testing import TestService
    from src.services.logging_service import LoggingService
    app=tmp_path/'isolated_app'; (app/'tests').mkdir(parents=True)
    (app/'tests/test_temp.py').write_text(
        'from pathlib import Path\n'
        'def test_temp_location(tmp_path):\n'
        '    assert tmp_path.is_relative_to(Path(__file__).resolve().parents[1]/"logs")\n',encoding='utf-8')
    tables=app/'output/tables'; tables.mkdir(parents=True)
    rows=TestService().run(app,tables,LoggingService(app))
    assert len(rows)==4 and all(row['passed'] for row in rows)


def test_rejected_output_path_does_not_write_outside_app(tmp_path):
    app=tmp_path/'app'; app.mkdir(); outside=tmp_path/'outside'
    cfg=PipelineConfig(app,tmp_path/'missing.pdf',tmp_path/'missing.csv',tmp_path/'lecture.pdf',outside,3)
    result=PipelineController(cfg).run()
    assert result['status']=='FAILED'
    assert not outside.exists()
    assert (app/'output/HARNESS_LOG.xlsx').is_file()
