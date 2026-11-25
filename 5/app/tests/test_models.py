import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from src.repositories import DataRepository, normalize
from src.services.inputs import DataValidationService, PdfExtractor
from src.services.analysis import ParetoAnalysis, ScenarioAnalysis
from src.calculators.optimizer import ProductionAndPortfolioOptimizer

APP = Path(__file__).resolve().parents[1]


class ModelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with TemporaryDirectory(dir=APP / "logs") as work:
            cls.csv = Path(work) / "inputs.csv"
            PdfExtractor().export(PdfExtractor.locate(APP), cls.csv)
            cls.op, cls.pf, cls.sc = DataRepository().load(cls.csv)
            DataValidationService().validate(cls.op, cls.pf, cls.sc, controls=True)
        cls.opt = ProductionAndPortfolioOptimizer()
        cls.base = cls.opt.solve_operational_milp(cls.op)
        cls.exact = cls.opt.solve_portfolio_knapsack(cls.pf)

    def test_source(self):
        self.assertEqual(tuple(p.yield_rate for p in self.op.products), (.85, .70, .90))
        self.assertEqual(self.op.material_coefficients[0], (170, 210, 90))
        self.assertEqual(self.pf.budget, 140)
        self.assertEqual(self.sc.stress_budget, 91)

    def test_invalid(self):
        def check(op=self.op, pf=self.pf, sc=self.sc):
            with self.assertRaises(ValueError):
                DataValidationService().validate(op, pf, sc)
        for y in (0, -1, 1.01, float("nan"), float("inf")):
            check(op=replace(self.op, products=(replace(self.op.products[0], yield_rate=y), *self.op.products[1:])))
        check(op=replace(self.op, machines=(replace(self.op.machines[0], capacity=-1), *self.op.machines[1:])))
        check(pf=replace(self.pf, projects=(self.pf.projects[0], *self.pf.projects[:-1])))
        check(pf=replace(self.pf, links=(("equal", 1, 99),)))
        check(sc=replace(self.sc, carbon_tax=-1))

    def test_currency(self):
        self.assertEqual(normalize("4500", "руб.", "тыс. руб."), 4.5)
        self.assertEqual(normalize("1,2", "млн руб.", "тыс. руб."), 1200)
        with self.assertRaises(ValueError):
            normalize("2", "кг", "тыс. руб.")

    def test_csv_tamper(self):
        with TemporaryDirectory(dir=APP / "logs") as work:
            path = Path(work) / "inputs.csv"
            PdfExtractor().export(PdfExtractor.locate(APP), path)
            raw = path.read_text(encoding="utf-8-sig")
            rows = raw.splitlines()
            for data in (rows + [rows[1]], rows[:1] + rows[2:], raw.replace("0,85", "0,84", 1).splitlines()):
                path.write_text("\n".join(data), encoding="utf-8-sig")
                with self.assertRaises(ValueError):
                    DataRepository().load(path)

    def test_operations(self):
        lp = self.opt.operations.relaxation(self.op)
        fixed = self.opt.extract_fixed_lp_duals(self.op, self.base.y)
        self.assertGreaterEqual(lp.objective + 1e-6, self.base.objective)
        self.assertAlmostEqual(fixed.objective, self.base.objective, places=5)
        self.assertLessEqual(self.base.gap, 1e-4)
        self.assertGreaterEqual(self.base.bound + 1e-6, self.base.objective)
        self.assertTrue(all(v >= -1e-6 for v in self.base.slack))
        self.assertEqual(self.base, self.opt.solve_operational_milp(self.op))

    def test_independent_certificate(self):
        independent = self.opt.operations.enumerate_modes(self.op)
        self.assertAlmostEqual(self.base.objective, independent.objective, places=5)
        self.assertEqual(self.base.y, independent.y)

    def test_duality(self):
        fixed = self.opt.extract_fixed_lp_duals(self.op, self.base.y)
        self.assertLess(max(abs(a*b) for a,b in zip(fixed.shadow, fixed.slack)), 1e-5)
        self.assertLess(max(abs(a*b) for a,b in zip(fixed.x, fixed.reduced)), 1e-5)
        for i, material in enumerate(self.op.materials):
            materials = list(self.op.materials)
            materials[i] = replace(material, capacity=material.capacity + 0.01)
            updated = self.opt.extract_fixed_lp_duals(replace(self.op, materials=tuple(materials)), self.base.y)
            self.assertAlmostEqual((updated.objective-fixed.objective)/.01, fixed.shadow[3+i], places=5)

    def test_yield_and_zero(self):
        op = replace(self.op, products=tuple(replace(p, yield_rate=1) for p in self.op.products))
        model = self.opt.operations.model(op)
        self.assertEqual(model.matrix[2,0], 0)
        np.testing.assert_allclose(model.matrix[:3], op.machine_coefficients)
        self.assertGreaterEqual(self.opt.solve_operational_milp(op).objective, self.base.objective)

    def test_zero_nmp(self):
        op = replace(self.op, materials=(replace(self.op.materials[0], capacity=0), self.op.materials[1]))
        result = self.opt.solve_operational_milp(op)
        self.assertEqual(result.x, (0,0,0))
        self.assertEqual(result.y, (0,0,0))
        self.assertEqual(result.objective, 0)

    def test_negative(self):
        op = replace(self.op, products=(replace(self.op.products[0], margin=-500), *self.op.products[1:]))
        result = self.opt.solve_operational_milp(op)
        fixed = self.opt.extract_fixed_lp_duals(op, result.y)
        self.assertAlmostEqual(result.x[0], 0)
        self.assertLessEqual(fixed.reduced[0], 1e-6)
        self.assertAlmostEqual(fixed.reduced[0], -500 - self.opt.operations.model(op).matrix[:,0] @ fixed.shadow)

    def test_extruder(self):
        result = self.opt.solve_operational_milp(self.op, forbidden=(3,))
        self.assertEqual(result.y[2], 0)
        self.assertEqual(result.x[1:], (0,0))
        self.assertGreater(result.x[0], self.base.x[0])
        self.assertLess(result.objective, self.base.objective)

    def test_exclusion(self):
        pf = replace(self.pf, links=self.pf.links + (("excludes",1,4),))
        result = self.opt.solve_portfolio_knapsack(pf)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertNotIn(4, result.ids)

    def test_certificate(self):
        feasible, examined = self.opt.portfolio.enumerate(self.pf)
        self.assertEqual(examined, 128)
        self.assertEqual(max(p.npv for p in feasible), self.exact.npv)
        self.assertLessEqual(self.exact.gap, 1e-4)
        self.assertGreaterEqual(self.exact.bound, self.exact.npv - 1e-7)

    def test_portfolio(self):
        port = self.opt.portfolio.metrics(self.pf, (1,4,5,7))
        self.assertTrue(self.opt.portfolio.feasible(self.pf, port))
        self.assertEqual((port.capex, port.npv, port.score), (120,90,320))
        for budget in (0,91,140):
            pf = replace(self.pf, budget=budget)
            result = self.opt.solve_portfolio_knapsack(pf)
            self.assertLessEqual(result.capex, budget)
            self.assertTrue(self.opt.portfolio.feasible(pf, result))
            self.assertTrue(self.opt.portfolio.feasible(pf, self.opt.portfolio.greedy(pf)[0]))
        self.assertEqual(self.opt.solve_portfolio_knapsack(replace(self.pf, budget=0)).ids, ())
        self.assertEqual(self.opt.solve_portfolio_knapsack(self.pf, score_floor=1000).status, "INFEASIBLE")

    def test_pareto(self):
        result = ParetoAnalysis(self.opt.portfolio).run(self.pf)
        frontier = result["frontier"]
        self.assertTrue(all(a.score < b.score and a.npv > b.npv for a,b in zip(frontier,frontier[1:])))
        self.assertEqual(result["epsilon"][0]["epsilon"], 0)
        self.assertEqual(result["epsilon"][-1]["epsilon"], max(p.score for p in frontier))
        self.assertEqual(len(result["mrt"]), len(frontier)-1)

    def test_stresses(self):
        result = ScenarioAnalysis(self.opt).stress(self.op, self.pf, self.sc, self.base, self.exact)
        self.assertLessEqual(result["finance"].capex, self.sc.stress_budget)
        self.assertGreaterEqual(result["green"].score, self.sc.score_floor)
        self.assertLess(result["carbon"].objective, self.base.objective)
        self.assertAlmostEqual(result["carbon_rows"][1]["delta_margin"], 4500 * 1.8 * (1/.7-1)/1000)
