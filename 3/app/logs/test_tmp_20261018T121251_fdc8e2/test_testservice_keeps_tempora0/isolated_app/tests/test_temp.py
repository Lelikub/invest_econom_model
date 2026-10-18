from pathlib import Path
def test_temp_location(tmp_path):
    assert tmp_path.is_relative_to(Path(__file__).resolve().parents[1]/"logs")
