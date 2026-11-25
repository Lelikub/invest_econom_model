import csv
import math
from pathlib import Path

from .models import InvestmentProject, Machine, Material, OperationalInputs, PortfolioInputs, Product, Scenario

MONEY = {"руб.": 1, "тыс. руб.": 1000, "млн руб.": 1000000}
COLUMNS = ("group", "id", "field", "page", "source_text", "source_unit", "value", "unit")


def normalize(raw, source_unit, unit):
    token = str(raw).replace(",", ".").replace("−", "-")
    if token.startswith("10^"):
        token = f"1e{int(token[3:])}"
    number = float(token)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite source number: {raw}")
    if source_unit == unit:
        return number
    if source_unit in MONEY and unit in MONEY:
        return number * MONEY[source_unit] / MONEY[unit]
    if source_unit == "%" and unit == "доля":
        return number / 100
    raise ValueError(f"Incompatible units: {source_unit!r}, {unit!r}")


def write_csv(path: Path, rows, columns=None):
    rows = list(rows)
    if columns is None:
        columns = list(dict.fromkeys(key for row in rows for key in row))
    if not columns:
        raise ValueError(f"Empty CSV schema: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


class DataRepository:
    def load(self, path):
        rows = read_csv(path)
        data = {}
        for row in rows:
            key = (row["group"], row["id"], row["field"])
            if key in data or not 1 <= int(row["page"]) <= 9:
                raise ValueError(f"Duplicate or bad PDF provenance: {key}")
            data[key] = row

        def get(group, index, field, unit):
            key = (group, str(index), field)
            if key not in data:
                raise ValueError(f"Missing CSV input: {key}")
            row = data.pop(key)
            if row["unit"] != unit or not row["source_text"]:
                raise ValueError(f"Bad unit or empty source: {key}")
            if unit == "text":
                if row["source_unit"] != unit or row["source_text"] != row["value"]:
                    raise ValueError(f"Text provenance mismatch: {key}")
                return row["value"]
            value = normalize(row["source_text"], row["source_unit"], unit)
            if value != float(row["value"]):
                raise ValueError(f"Numeric provenance mismatch: {key}")
            if unit in {"ID", "балл"}:
                if not value.is_integer():
                    raise ValueError(f"Expected integer: {key}")
                return int(value)
            return value

        products = tuple(Product(i, get("product", i, "name", "text"), get("product", i, "code", "text"),
                                 get("product", i, "margin", "тыс. руб."), get("product", i, "yield", "доля"))
                         for i in range(1, 4))
        machines = tuple(Machine(i, get("machine", i, "name", "text"), get("machine", i, "capacity", "маш.-ч"),
                                 get("machine", i, "fixed_cost", "тыс. руб.")) for i in range(1, 4))
        materials = tuple(Material(i, get("material", i, "name", "text"), get("material", i, "capacity", unit), unit)
                          for i, unit in enumerate(("л", "кг"), 1))
        matrix = [tuple(get("matrix", i, str(j), unit) for j in range(1, 4))
                  for i, unit in enumerate(("маш.-ч/т",)*3 + ("л/т", "кг/т"), 1)]
        projects = tuple(InvestmentProject(i, get("project", i, "name", "text"), get("project", i, "capex", "млн руб."),
                                           get("project", i, "npv", "млн руб."), get("project", i, "score", "балл"))
                         for i in range(1, 8))

        def link(i):
            return get("link", i, "kind", "text"), get("link", i, "left", "ID"), get("link", i, "right", "ID")

        op = OperationalInputs(products, machines, materials, tuple(matrix[:3]), tuple(matrix[3:]))
        pf = PortfolioInputs(projects, get("portfolio", 0, "budget", "млн руб."), tuple(link(i) for i in range(1, 4)))
        fields = (("zero_nmp", "л"), ("negative_margin", "тыс. руб."), ("forbidden_machine", "ID"),
                  ("stress_budget", "млн руб."), ("budget_cut", "доля"), ("npv_cut", "доля"),
                  ("carbon_tax", "руб."), ("emission_factor", "т CO2/т"), ("score_floor", "балл"),
                  ("epsilon_step", "балл"), ("mrt_limit", "млн руб./балл"), ("gap_limit", "доля"))
        sc = Scenario(extra_link=link(4), **{field: get("scenario", 0, field, unit) for field, unit in fields})
        if data:
            raise ValueError(f"Unexpected CSV inputs: {list(data)}")
        return op, pf, sc
