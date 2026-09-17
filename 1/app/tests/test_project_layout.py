"""Repository-level contract for the assignment's directory layout."""

from pathlib import Path


def test_all_project_materials_live_under_assignment_directory():
    assignment_root = Path(__file__).resolve().parents[2]

    assert assignment_root.name == "1"
    assert (assignment_root / "data" / "data.csv").is_file()
    assert (assignment_root / "task").is_dir()
    assert (assignment_root / "docs").is_dir()
    assert (
        assignment_root / "reports" / "Итоговый_отчет_ФИП_оформленный.docx"
    ).is_file()
