import math
from pathlib import Path
from tempfile import TemporaryDirectory

import pulp

from .operations import OperatingModel, OperationsOptimizer


class CbcCertificate:
    def __init__(self, logs):
        self.logs = Path(logs)

    @staticmethod
    def solver(work, gap_limit):
        # Keep CBC inputs and the verbose solver trace within the application.
        cmd = pulp.PULP_CBC_CMD(msg=False, gapRel=gap_limit, logPath=str(Path(work)/"cbc.log"), threads=1)
        cmd.tmpDir = str(work)
        return cmd

    def operations(self, inputs, gap_limit, continuous=False, fixed_y=None):
        model: OperatingModel = OperationsOptimizer.model(inputs)
        problem = pulp.LpProblem("Production", pulp.LpMaximize)
        x = [pulp.LpVariable(f"x{i}",lowBound=0) for i in range(1,4)]
        y = [pulp.LpVariable(f"y{i}",lowBound=0,upBound=1,cat=pulp.LpContinuous if continuous else pulp.LpBinary)
             for i in range(1,4)]
        if fixed_y is not None:
            for v, flag in zip(y, fixed_y):
                v.setInitialValue(flag)
                v.fixValue()
        problem += pulp.lpSum(c*v for c,v in zip(model.objective_vector,x+y))
        for row,rhs in zip(model.augmented,model.rhs):
            problem += pulp.lpSum(float(c)*v for c,v in zip(row,x+y)) <= float(rhs)
        with TemporaryDirectory(dir=self.logs) as work:
            problem.solve(self.solver(work,gap_limit))
            name = "cbc_fixed.log" if fixed_y is not None else ("cbc_lp.log" if continuous else "cbc_milp.log")
            (self.logs/name).write_bytes((Path(work)/"cbc.log").read_bytes())
        if problem.status != pulp.LpStatusOptimal or problem.sol_status != pulp.LpSolutionOptimal:
            raise RuntimeError(f"CBC production did not certify an optimum: {pulp.LpStatus[problem.status]}")
        return pulp.value(problem.objective)

    def portfolio(self, inputs, gap_limit):
        p = pulp.LpProblem("Portfolio",pulp.LpMaximize)
        z = {project.id:pulp.LpVariable(f"z{project.id}",cat=pulp.LpBinary) for project in inputs.projects}
        p += pulp.lpSum(project.npv*z[project.id] for project in inputs.projects)
        p += pulp.lpSum(project.capex*z[project.id] for project in inputs.projects) <= inputs.budget
        for kind,a,b in inputs.links:
            if kind == "excludes":
                p += z[a]+z[b] <= 1
            elif kind == "requires":
                p += z[a] <= z[b]
            else:
                p += z[a] == z[b]
        with TemporaryDirectory(dir=self.logs) as work:
            p.solve(self.solver(work,gap_limit))
            (self.logs/"cbc_portfolio.log").write_bytes((Path(work)/"cbc.log").read_bytes())
        if p.status != pulp.LpStatusOptimal or p.sol_status != pulp.LpSolutionOptimal:
            raise RuntimeError(f"CBC portfolio did not certify an optimum: {pulp.LpStatus[p.status]}")
        result = pulp.value(p.objective)
        if not math.isfinite(result):
            raise RuntimeError("CBC portfolio objective is non-finite")
        return result
