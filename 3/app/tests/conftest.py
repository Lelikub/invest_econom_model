import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pytest

@pytest.fixture(scope='session')
def inputs(tmp_path_factory):
    from src.services.extraction import PdfExtractionService
    from src.repositories import DataRepository
    root=tmp_path_factory.mktemp('pdf_inputs')
    PdfExtractionService().extract(next((APP.parent/'data').glob('*.pdf')),root)
    return DataRepository.load(root)
