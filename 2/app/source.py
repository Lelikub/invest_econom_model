"""Programmatic PDF extraction and provenance-preserving CSV export."""
from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from model import ProjectInputData


SOURCE_NAMES = {
    "I0": ("Начальный CAPEX 1-й очереди", "млн долл.", "CAPEX первой очереди"),
    "S0": ("Базовые денежные потоки", "млн долл.", "PV потоков первой очереди"),
    "K": ("Цена исполнения (K)", "млн долл.", "CAPEX второй очереди"),
    "r": ("безрисковая ставка", "доля/год", "Непрерывная безрисковая ставка"),
    "sigma": ("рыночная волатильность", "доля/год", "Годовая волатильность"),
    "delta": ("издержки устаревания", "доля/год", "Стоимость отсрочки"),
    "T": ("горизонт T", "год", "Срок опциона"),
    "N": ("число шагов N", "шаг", "Число шагов CRR"),
    "m": ("удваивает выпуск продукции", "доля", "Масштаб дополнительных потоков"),
}


def extract_pdf(pdf: Path) -> list[str]:
    exe = shutil.which("pdftotext") or r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"
    if not Path(exe).is_file():
        raise RuntimeError("pdftotext is required for PDF extraction")
    with tempfile.TemporaryDirectory() as temp_dir:
        out = Path(temp_dir) / "extracted.txt"
        subprocess.run([exe, "-layout", "-enc", "UTF-8", str(pdf), str(out)], capture_output=True, check=True)
        return out.read_text(encoding="utf-8", errors="replace").split("\f")


def _match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    if not match:
        raise ValueError(f"Required input missing in PDF: {pattern}")
    return match.group(1)


def parse_inputs(pages: list[str], pdf: Path, csv_path: Path) -> ProjectInputData:
    # Page 5 contains the assignment inputs. These anchors stop a change in PDF
    # layout from silently turning a nearby worked example into model inputs.
    candidates = [(i + 1, p) for i, p in enumerate(pages) if "Исходные данные практической работы" in p]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one source input section")
    page_no, text = candidates[0]
    patterns = {
        "I0": r"Начальный CAPEX 1-й очереди[^:]*:\s*([\d,]+)",
        "S0": r"Базовые денежные потоки[^:]*:\s*([\d,]+)",
        "K": r"Цена исполнения \(K\):\s*([\d,]+)",
        "r": r"безрисковая ставка[^=]*=\s*([\d,]+)%",
        "sigma": r"рыночная волатильность[^=]*=\s*([\d,]+)%",
        "delta": r"издержки устаревания[^=]*=\s*([\d,]+)%",
        "T": r"горизонт T\s*=\s*([\d,]+)\s*года",
        "N": r"число шагов N\s*=\s*([\d,]+)",
        "m": r"удваивает выпуск\s+продукции\s*\(\+([\d,]+)%\)",
    }
    rows = []
    values = {}
    for symbol, pattern in patterns.items():
        raw = _match(text, pattern)
        numeric = float(raw.replace(",", "."))
        if symbol in ("r", "sigma", "delta", "m"):
            numeric /= 100
        values[symbol] = int(numeric) if symbol == "N" else numeric
        anchor, unit, description = SOURCE_NAMES[symbol]
        rows.append({"parameter": anchor, "symbol": symbol, "raw_value": raw + ("%" if symbol in ("r", "sigma", "delta", "m") else ""), "normalized_value": numeric, "unit": unit, "description": description, "source_file": pdf.name, "source_page": page_no, "extraction_method": "pdftotext + anchored regex", "confidence": "high", "notes": "Decimal comma normalized; percentages divided by 100" if symbol in ("r", "sigma", "delta", "m") else "Decimal comma normalized"})
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    return load_csv(csv_path)


def load_csv(path: Path) -> ProjectInputData:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    symbols = [r["symbol"] for r in rows]
    if len(symbols) != len(set(symbols)) or set(symbols) != set(SOURCE_NAMES):
        raise ValueError("Missing or duplicated CSV parameters")
    values = {r["symbol"]: float(r["normalized_value"]) for r in rows}
    if not values["N"].is_integer():
        raise ValueError("N must be an integer in source CSV")
    values["N"] = int(values["N"])
    data = ProjectInputData(**values)
    data.validate()
    return data
