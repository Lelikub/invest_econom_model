from pathlib import Path
import sys
import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

@pytest.fixture(scope='session')
def inputs(tmp_path_factory):
    from src.services.extraction import PdfExtractionService
    from src.repositories import DataRepository
    dest = tmp_path_factory.mktemp('inputs')
    source = APP / 'data/source_assignment.pdf'
    if not source.exists():
        source = next((APP.parent / 'data').glob('*.pdf'))
    PdfExtractionService().extract(source, dest)
    return DataRepository.load(dest)
