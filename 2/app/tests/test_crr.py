import sys
import site
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
vendor=Path(__file__).resolve().parents[3]/"1"/"app"/".python-packages"
if vendor.is_dir():site.addsitedir(str(vendor))
from model import ArbitrageConditionError, ProjectInputData, calculate


class CRRTests(unittest.TestCase):
    def setUp(self):
        self.data=ProjectInputData(125,115,90,.06,.35,.05,3,3,1)
        self.result=calculate(self.data)

    def test_input_validation(self):
        with self.assertRaises(ValueError):calculate(self.data.changed(S0=-1))
        with self.assertRaises(ValueError):calculate(self.data.changed(N=0))
        with self.assertRaises(ValueError):calculate(self.data.changed(m=0))

    def test_dt(self):self.assertEqual(self.result.params.dt,1)
    def test_up_factor(self):self.assertAlmostEqual(self.result.params.u,1.4190675485932571)
    def test_down_factor(self):self.assertAlmostEqual(self.result.params.d,1/self.result.params.u)
    def test_recombination(self):self.assertAlmostEqual(self.result.params.u*self.result.params.d,1)
    def test_probability_range(self):self.assertTrue(0<self.result.params.p<1)
    def test_asset_lattice_root(self):
        self.assertEqual(self.result.asset[0][0],115)
        self.assertEqual(sum(map(len,self.result.asset)),10)
    def test_terminal_payoff(self):
        self.assertEqual(self.result.option[3][3].C,max(self.result.asset[3][3]-90,0))
    def test_backward_induction(self):
        for row in self.result.option[:-1]:
            for n in row:self.assertAlmostEqual(n.C,max(n.intrinsic,n.continuation))
    def test_american_option_condition(self):
        for row in self.result.option[:-1]:
            for n in row:self.assertEqual(n.decision=="EXERCISE",n.intrinsic>n.continuation)
    def test_rov(self):self.assertAlmostEqual(self.result.rov,35.85991990301939)
    def test_strategic_npv(self):self.assertAlmostEqual(self.result.npv_strat,25.85991990301939)
    def test_zero_sigma_rejected(self):
        with self.assertRaises(ArbitrageConditionError):calculate(self.data.changed(sigma=0))
    def test_arbitrage_violation(self):
        with self.assertRaises(ArbitrageConditionError):calculate(self.data.changed(r=1.6,N=1))
    def test_probability_override(self):
        test=calculate(self.data,p_override=1)
        self.assertEqual(test.params.p,1)
        self.assertNotEqual(test.rov,self.result.rov)
    def test_arbitrary_n(self):
        x=calculate(self.data.changed(N=12))
        self.assertEqual(sum(map(len,x.asset)),91)
        self.assertEqual(len(x.option),13)
    def test_excel_python_reconciliation(self):
        from tempfile import TemporaryDirectory
        from excel import reconcile
        workbook=Path(__file__).resolve().parents[1]/"output"/"Ground_Truth_ROA.xlsx"
        if not workbook.exists():self.skipTest("Run pipeline to create Excel Ground Truth")
        with TemporaryDirectory() as tmp:
            rows=reconcile(self.result,workbook,Path(tmp)/"reconciliation.csv")
        if all(r["status"]=="NOT_VERIFIED" for r in rows):
            self.skipTest("Excel workbook has not been recalculated")
        self.assertEqual(len(rows),28)
        self.assertTrue(all(r["status"]=="PASS" for r in rows))


if __name__=="__main__":unittest.main()
