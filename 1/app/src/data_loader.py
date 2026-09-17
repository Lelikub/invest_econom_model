"""Strict reader and validator for the assignment CSV input."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from .models import EquipmentItem, InputConflict, ProjectData, ValidationRecord


class DataValidationError(ValueError):
    """Raised when input data cannot form an unambiguous project model."""


REQUIRED_COLUMNS = {"Category", "Item", "Value"}
REQUIRED_PARAMETERS = {
    "lang_factor",
    "working_capital_share",
    "wacc",
    "tax_rate",
    "project_lifetime_years",
}
KNOWN_CATEGORIES = {"Equipment_Cost", "Parameter", "Revenue_Profile", "OPEX_Profile"}
YEAR_PATTERN = re.compile(r"^Year_(\d+)$")
PDF_CONTROL_VALUES = {
    "wacc": (0.10, "Задание, этап 1"),
    "working_capital_share": (0.12, "Задание, этап 1"),
}


def load_project_data(path: Path) -> ProjectData:
    """Load and validate a project CSV without modifying the source file."""

    source = Path(path)
    if not source.is_file():
        raise DataValidationError(f"CSV-файл не найден: {source}")

    rows = _read_rows(source)
    equipment: list[EquipmentItem] = []
    parameters: dict[str, float] = {}
    revenue: dict[int, float] = {}
    opex: dict[int, float] = {}
    seen: set[tuple[str, str]] = set()

    for line_number, row in rows:
        category = row["Category"].strip()
        item = row["Item"].strip()
        raw_value = row["Value"].strip()
        if not category or not item or not raw_value:
            raise DataValidationError(f"Строка {line_number}: обнаружено пустое обязательное значение")
        if category not in KNOWN_CATEGORIES:
            raise DataValidationError(f"Строка {line_number}: неизвестная категория {category!r}")

        key = (category, item)
        if key in seen:
            raise DataValidationError(f"Строка {line_number}: параметр {category}/{item} дублируется")
        seen.add(key)
        value = _parse_number(raw_value, line_number)

        if category == "Equipment_Cost":
            if value < 0:
                raise DataValidationError(f"Строка {line_number}: стоимость оборудования не может быть отрицательной")
            equipment.append(EquipmentItem(item, value))
        elif category == "Parameter":
            parameters[item] = value
        elif category == "Revenue_Profile":
            revenue[_parse_year(item, line_number)] = value
        else:
            opex[_parse_year(item, line_number)] = value

    _validate_required_inputs(equipment, parameters)
    lifetime = _validate_parameter_ranges(parameters)
    _validate_profile("Revenue_Profile", revenue, lifetime)
    _validate_profile("OPEX_Profile", opex, lifetime)

    conflicts = tuple(
        InputConflict(field, pdf_value, parameters[field], pdf_source)
        for field, (pdf_value, pdf_source) in PDF_CONTROL_VALUES.items()
        if not math.isclose(parameters[field], pdf_value, rel_tol=0.0, abs_tol=1e-12)
    )
    validations = (
        ValidationRecord("Структура CSV", "PASS", "Обязательные столбцы Category, Item, Value присутствуют"),
        ValidationRecord("Уникальность", "PASS", "Дублирующиеся пары Category/Item отсутствуют"),
        ValidationRecord("Типы и диапазоны", "PASS", "Числовые значения и диапазоны параметров корректны"),
        ValidationRecord("Горизонт", "PASS", f"Профили Revenue/OPEX полностью покрывают годы 1–{lifetime}"),
    )

    return ProjectData(
        equipment=tuple(equipment),
        lang_factor=parameters["lang_factor"],
        working_capital_share=parameters["working_capital_share"],
        wacc=parameters["wacc"],
        tax_rate=parameters["tax_rate"],
        project_lifetime_years=lifetime,
        revenue=dict(sorted(revenue.items())),
        opex=dict(sorted(opex.items())),
        conflicts=conflicts,
        validations=validations,
        source_path=source.resolve(),
    )


def _read_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fieldnames = set(reader.fieldnames or ())
            if not REQUIRED_COLUMNS.issubset(fieldnames):
                missing = ", ".join(sorted(REQUIRED_COLUMNS - fieldnames))
                raise DataValidationError(f"Отсутствуют обязательные столбцы CSV: {missing}")
            rows = [(line_number, row) for line_number, row in enumerate(reader, start=2)]
    except UnicodeDecodeError as exc:
        raise DataValidationError("CSV должен быть сохранен в UTF-8") from exc
    if not rows:
        raise DataValidationError("CSV не содержит строк данных")
    return rows


def _parse_number(raw_value: str, line_number: int) -> float:
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError as exc:
        raise DataValidationError(f"Строка {line_number}: Value должен быть числом") from exc
    if not math.isfinite(value):
        raise DataValidationError(f"Строка {line_number}: Value должен быть конечным числом")
    return value


def _parse_year(item: str, line_number: int) -> int:
    match = YEAR_PATTERN.fullmatch(item)
    if match is None:
        raise DataValidationError(f"Строка {line_number}: год должен иметь формат Year_N")
    year = int(match.group(1))
    if year < 1:
        raise DataValidationError(f"Строка {line_number}: номер года должен быть положительным")
    return year


def _validate_required_inputs(equipment: list[EquipmentItem], parameters: dict[str, float]) -> None:
    if not equipment:
        raise DataValidationError("Категория Equipment_Cost не содержит оборудования")
    missing = REQUIRED_PARAMETERS - parameters.keys()
    if missing:
        raise DataValidationError(f"Отсутствуют обязательные параметры: {', '.join(sorted(missing))}")


def _validate_parameter_ranges(parameters: dict[str, float]) -> int:
    if parameters["lang_factor"] <= 0:
        raise DataValidationError("lang_factor должен быть больше нуля")
    if not 0 <= parameters["working_capital_share"] < 1:
        raise DataValidationError("working_capital_share должен находиться в диапазоне [0, 1)")
    if parameters["wacc"] < 0:
        raise DataValidationError("wacc не может быть отрицательным")
    if not 0 <= parameters["tax_rate"] < 1:
        raise DataValidationError("tax_rate должен находиться в диапазоне [0, 1)")

    raw_lifetime = parameters["project_lifetime_years"]
    if raw_lifetime <= 0 or not raw_lifetime.is_integer():
        raise DataValidationError("project_lifetime_years должен быть положительным целым числом")
    return int(raw_lifetime)


def _validate_profile(name: str, profile: dict[int, float], lifetime: int) -> None:
    expected = set(range(1, lifetime + 1))
    actual = set(profile)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise DataValidationError(f"{name} не соответствует горизонту: пропущены {missing}, лишние {extra}")

