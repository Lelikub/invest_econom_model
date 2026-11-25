import math
import re
import unicodedata
from numbers import Real
from pathlib import Path

import pymupdf

from ..repositories import COLUMNS, normalize, write_csv

PDF_NAME = "Задание_к_практическому_занятию_5_ФИП.pdf"
LECTURE_NAME = "Лекция 9 ФИП слайды.pdf"
TEMPLATE_NAME = "Шаблон_отчета_ЭА_краткий_v2 (3).docx"
NUM = r"[−-]?\d+(?:[,.]\d+)?"


def match(pattern, text):
    found = re.search(pattern, text)
    if found is None:
        raise ValueError(f"Expected PDF pattern not found: {pattern}")
    return found.groups()


def clean(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


class PdfExtractor:
    @staticmethod
    def locate(app):
        for path in (app.parent / "task" / PDF_NAME, app.parent / "data" / PDF_NAME, app / "data" / "source_assignment.pdf"):
            if path.is_file():
                return path
        raise FileNotFoundError(PDF_NAME)

    def export(self, pdf, csv_path):
        with pymupdf.open(pdf) as doc:
            if len(doc) != 9:
                raise ValueError(f"Unexpected assignment page count: {len(doc)}")
            raw = {i: page.get_text() for i, page in enumerate(doc, 1)}
        page = {i: clean(text) for i, text in raw.items()}
        rows = []

        def put(group, index, field, p, text, unit, source_unit=None):
            source_unit = source_unit or unit
            value = text if unit == "text" else normalize(text.replace("−", "-"), source_unit, unit)
            rows.append(dict(zip(COLUMNS, (group, index, field, p, text, source_unit, value, unit))))

        for i in range(1, 4):
            name, code, margin, yield_rate, yield_percent = match(
                rf"Продукт {i} \(j\s*=\s*{i}\): (.*?)\s+\(([ЭПК]-{i})\)\. Маржа:.*?=\s*({NUM})\s+тыс\.\s+руб\./т\..*?Y{i}\s*=\s*({NUM})\s*\(({NUM})%\)",
                page[2])
            if normalize(yield_percent, "%", "доля") != normalize(yield_rate, "доля", "доля"):
                raise ValueError(f"Inconsistent yield on PDF page 2: product {i}")
            for field, value, unit in (("name", name, "text"), ("code", code, "text"),
                                       ("margin", margin, "тыс. руб."), ("yield", yield_rate, "доля")):
                put("product", i, field, 2, value, unit)
            p = 2 if i < 3 else 3
            name, capacity, fixed = match(
                rf"Агрегат {i} \(k\s*=\s*{i}\): (.*?)\. Доступный фонд.*?: b{i}\s*=\s*({NUM})\s+маш\.-часов/квартал.*?F{i}\s*=\s*({NUM})\s+тыс\.\s+руб\./квартал",
                page[p])
            for field, value, unit in (("name", name, "text"), ("capacity", capacity, "маш.-ч"), ("fixed_cost", fixed, "тыс. руб.")):
                put("machine", i, field, p, value, unit)

        for i, label, unit in ((1, "литров", "л"), (2, "кг", "кг")):
            name, cap = match(rf"Сырьё {i} \(r\s*=\s*{i}\): (.*?)\. Доступный складской запас: B{i}\s*=\s*({NUM})\s+{label}", page[3])
            put("material", i, "name", 3, name, "text")
            put("material", i, "capacity", 3, cap, unit)
        table = page[3].split("Нормативная матрица", 1)[1].split("Правило задания", 1)[0]
        for i, label, unit, pdf_unit in (
            (1, "Агрегат 1", "маш.-ч/т", "маш.-ч/т"), (2, "Агрегат 2", "маш.-ч/т", "маш.-ч/т"),
            (3, "Агрегат 3", "маш.-ч/т", "маш.-ч/т"), (4, "Растворитель NMP", "л/т", "л/т"),
            (5, "Наномодификатор", "кг/т", "кг/т"),
        ):
            numbers = match(rf"{label}\s+\([ag]\s*\d,\s*j\),\s*{re.escape(pdf_unit)}\s+({NUM})\s+({NUM})\s+({NUM})", table)
            for j, number in enumerate(numbers, 1):
                put("matrix", i, str(j), 3, number, unit)

        projects = page[4].split("(из 100)", 1)[1].split("Топологические и технологические", 1)[0]
        for i in range(1, 8):
            name, cap, npv, score = match(
                rf"(?:^|\s){i}\s+([^\d].*?)\s+({NUM})\s+({NUM})\s+({NUM})(?=\s+{i+1}\s+[А-ЯЁ]|$)", projects.strip())
            for field, value, unit in (("name", name, "text"), ("capex", cap, "млн руб."), ("npv", npv, "млн руб."), ("score", score, "балл")):
                put("project", i, field, 4, value, unit)

        (budget,) = match(rf"B\s*inv\s*=\s*({NUM})\s+млн руб", page[3])
        put("portfolio", 0, "budget", 3, budget, "млн руб.")
        links = (
            (4, "excludes", r"Проекты No(\d+) и No(\d+) представляют"),
            (5, "requires", r"Проект No(\d+) не может быть реализован без Проекта No(\d+)"),
            (5, "equal", r"Проекты No(\d+).*?и No(\d+).*?образуют единый экологический"),
            (7, "excludes", r"взаимоисключения между Проектом No(\d+) и Проектом No(\d+)"),
        )
        for i, (p, kind, pattern) in enumerate(links, 1):
            left, right = match(pattern, page[p])
            for field, value, unit in (("kind", kind, "text"), ("left", left, "ID"), ("right", right, "ID")):
                put("link", i, field, p, value, unit)

        (gap_mantissa, gap_exponent) = match(r"MIPGap≤(10)\s*[−-](\d+)", page[6])
        gap_number = f"{gap_mantissa}^−{gap_exponent}"
        # PDF prints 10⁻⁴. Convert the base/exponent notation, retaining the original token.
        specs = (
            (7, "zero_nmp", r"B\s*1\s*=\s*(0)", "л", None),
            (7, "negative_margin", rf"c\s*1\s*=\s*({NUM})", "тыс. руб.", None),
            (7, "forbidden_machine", r"y\s*(\d+)\s*=\s*0", "ID", None),
            (7, "epsilon_step", r"∆ε\s*m\s*=\s*(\d+)", "балл", None),
            (8, "stress_budget", r"с\s+\d+ до (\d+) млн руб", "млн руб.", None),
            (8, "budget_cut", r"сокращён на (\d+)%", "доля", "%"),
            (8, "npv_cut", r"эффекты всех проектов на (\d+)%", "доля", "%"),
            (8, "carbon_tax", r"T\s*carbon\s*=\s*(\d+)\s+руб", "руб.", None),
            (8, "emission_factor", rf"e\s*waste\s*=\s*({NUM})\s+т CO2", "т CO2/т", None),
            (8, "score_floor", r"не менее (\d+) баллов", "балл", None),
            (9, "mrt_limit", rf"уступки менее ({NUM}) млн руб", "млн руб./балл", None),
        )
        for p, field, pattern, unit, original_unit in specs:
            (value,) = match(pattern, page[p])
            put("scenario", 0, field, p, value, unit, original_unit)
        put("scenario", 0, "gap_limit", 6, gap_number, "доля")
        write_csv(csv_path, rows, COLUMNS)
        return rows


class DataValidationService:
    @staticmethod
    def number(value, name, minimum=None, maximum=None):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"Invalid finite number: {name}={value!r}")
        if minimum is not None and value < minimum or maximum is not None and value > maximum:
            raise ValueError(f"Out of range: {name}={value}")

    def validate_operations(self, op):
        self.entities(op.products, 3)
        self.entities(op.machines, 3)
        self.entities(op.materials, 2)
        if len(set(p.code for p in op.products)) != 3 or any(m.unit != unit for m, unit in zip(op.materials, ("л", "кг"))):
            raise ValueError("Duplicate product code or incompatible material units")
        for p in op.products:
            self.number(p.margin, "margin")
            self.number(p.yield_rate, "yield", 0, 1)
            if p.yield_rate == 0:
                raise ValueError("Yield is zero")
        for m in op.machines:
            self.number(m.fixed_cost, "fixed cost", 0)
        for r in (*op.machines, *op.materials):
            self.number(r.capacity, "resource capacity", 0)
        for matrix, size in ((op.machine_coefficients, 3), (op.material_coefficients, 2)):
            if len(matrix) != size or any(len(row) != 3 for row in matrix):
                raise ValueError("Technology matrix dimensions are not 3×3 or 2×3")
            for row in matrix:
                for value in row:
                    self.number(value, "technology coefficient", 0)
        if any(not any(column) for column in zip(*op.machine_coefficients, *op.material_coefficients)):
            raise ValueError("A product has no resource coefficients")

    @staticmethod
    def entities(entities, count):
        if tuple(e.id for e in entities) != tuple(range(1, count+1)):
            raise ValueError("Missing, duplicate or unordered identifiers")
        if len({e.name for e in entities}) != count or any(not e.name.strip() for e in entities):
            raise ValueError("Empty or duplicate entity names")

    def validate_portfolio(self, pf):
        self.entities(pf.projects, 7)
        self.number(pf.budget, "budget", 0)
        for p in pf.projects:
            self.number(p.capex, "CAPEX", 0)
            self.number(p.npv, "NPV")
            self.number(p.score, "MCDA", 0, 100)
            if p.capex == 0 or type(p.score) is not int:
                raise ValueError("CAPEX must be positive and MCDA must be integer")
        keys = set()
        for kind, a, b in pf.links:
            key = (kind, a, b) if kind == "requires" else (kind, min(a,b), max(a,b))
            if kind not in {"excludes", "requires", "equal"} or a == b or a not in range(1,8) or b not in range(1,8) or key in keys:
                raise ValueError(f"Invalid or duplicate logical link: {(kind, a, b)}")
            keys.add(key)

    def validate(self, op, pf, sc, *, controls=False):
        self.validate_operations(op)
        self.validate_portfolio(pf)
        for field in ("zero_nmp", "stress_budget", "carbon_tax", "emission_factor", "score_floor", "mrt_limit"):
            self.number(getattr(sc, field), field, 0)
        self.number(sc.negative_margin, "negative margin", maximum=0)
        self.number(sc.budget_cut, "budget cut", 0, 1)
        self.number(sc.npv_cut, "NPV cut", 0, 1)
        self.number(sc.gap_limit, "MIP gap limit", 0, 1e-4)
        if abs(pf.budget * (1-sc.budget_cut) - sc.stress_budget) > 1e-8:
            raise ValueError("Stress budget conflicts with percentage cut")
        if sc.forbidden_machine not in range(1,4) or type(sc.epsilon_step) is not int or sc.epsilon_step <= 0:
            raise ValueError("Invalid stress index or epsilon step")
        from dataclasses import replace
        self.validate_portfolio(replace(pf, links=pf.links+(sc.extra_link,)))
        if controls:
            facts = (tuple(p.yield_rate for p in op.products), tuple(m.capacity for m in op.machines),
                     tuple(m.capacity for m in op.materials), pf.budget, pf.links)
            expected = ((.85,.70,.90), (600,500,450), (12000,1500), 140,
                        (("excludes",2,3), ("requires",4,1), ("equal",5,7)))
            if facts != expected:
                raise ValueError(f"PDF control totals mismatch: {facts}")
