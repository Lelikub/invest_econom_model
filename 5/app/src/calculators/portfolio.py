from itertools import product

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from .operations import TOL, check_mip
from ..models import PortfolioResult
from ..services.inputs import DataValidationService


class PortfolioOptimizer:
    def __init__(self, gap_limit=1e-4):
        self.gap_limit = gap_limit

    @staticmethod
    def index(project):
        return 1 + project.npv / project.capex

    @staticmethod
    def metrics(inputs, ids, status="FEASIBLE", bound=None, gap=None):
        selected = [p for p in inputs.projects if p.id in ids]
        capex = sum(p.capex for p in selected)
        return PortfolioResult(tuple(p.id for p in selected), capex, sum(p.npv for p in selected),
                               sum(p.score for p in selected), inputs.budget-capex, status, bound, gap)

    @staticmethod
    def feasible(inputs, result, score_floor=None):
        if result.capex > inputs.budget+TOL or (score_floor is not None and result.score < score_floor):
            return False
        selected = set(result.ids)
        for kind, left, right in inputs.links:
            a, b = left in selected, right in selected
            if (kind == "excludes" and a and b or kind == "requires" and a and not b
                    or kind == "equal" and a != b):
                return False
        return True

    def enumerate(self, inputs):
        DataValidationService().validate_portfolio(inputs)
        examined = 0
        feasible = []
        for bits in product((0,1),repeat=len(inputs.projects)):
            examined += 1
            result = self.metrics(inputs, tuple(p.id for p, take in zip(inputs.projects,bits) if take))
            if self.feasible(inputs,result):
                feasible.append(result)
        return feasible, examined

    def greedy(self, inputs):
        DataValidationService().validate_portfolio(inputs)
        selected = set()
        attempts = []
        for p in sorted(inputs.projects, key=lambda p: (-self.index(p),p.id)):
            if p.id in selected:
                attempts.append({"id":p.id, "pi":self.index(p), "decision":"ALREADY_SELECTED",
                                 "bundle":str(p.id), "capex_after":self.metrics(inputs, selected).capex})
                continue
            bundle = {p.id}
            previous = set()
            while previous != bundle:
                previous = bundle.copy()
                for kind,a,b in inputs.links:
                    if kind in {"requires","equal"} and a in bundle:
                        bundle.add(b)
                    if kind == "equal" and b in bundle:
                        bundle.add(a)
            candidate = self.metrics(inputs, selected|bundle)
            increment = candidate.npv-self.metrics(inputs,selected).npv
            accepted = self.feasible(inputs,candidate) and increment > 0
            if accepted:
                selected.update(bundle)
            attempts.append({"id":p.id, "pi":self.index(p), "decision":"ACCEPTED" if accepted else "REJECTED",
                             "bundle":"+".join(map(str,sorted(bundle))), "candidate_capex":candidate.capex,
                             "incremental_npv":increment, "capex_after":self.metrics(inputs, selected).capex})
        return self.metrics(inputs,selected,status="GREEDY_FEASIBLE"), attempts

    def solve(self, inputs, score_floor=None):
        DataValidationService().validate_portfolio(inputs)
        projects = inputs.projects
        capex = np.array([p.capex for p in projects])
        npv = np.array([p.npv for p in projects])
        score = np.array([p.score for p in projects])
        rows, lower, upper = [capex], [-np.inf], [inputs.budget]
        for kind, a, b in inputs.links:
            line = np.zeros(len(projects))
            line[a-1] = 1
            line[b-1] = 1 if kind == "excludes" else -1
            rows.append(line)
            lower.append(0 if kind == "equal" else -np.inf)
            upper.append(1 if kind == "excludes" else 0)
        if score_floor is not None:
            DataValidationService().number(score_floor,"score floor",0)
            rows.append(score)
            lower.append(score_floor)
            upper.append(np.inf)
        r = milp(-npv, integrality=np.ones(len(projects)), bounds=Bounds(0,1),
                 constraints=LinearConstraint(np.asarray(rows), lower, upper),
                 options={"mip_rel_gap":self.gap_limit})
        if r.status == 2:
            return self.metrics(inputs,(),status="INFEASIBLE")
        if not r.success or r.x is None:
            raise RuntimeError(r.message)
        mask = np.rint(r.x)
        if np.max(np.abs(mask-r.x)) > TOL or np.any(mask < 0) or np.any(mask > 1):
            raise RuntimeError("Portfolio binary feasibility audit failed")
        bound, gap = check_mip(r, -r.fun, self.gap_limit)
        result = self.metrics(inputs,tuple(p.id for p, take in zip(projects,mask) if take), "OPTIMAL",bound,gap)
        if not self.feasible(inputs,result,score_floor) or abs(result.npv+r.fun)>TOL:
            raise RuntimeError("Portfolio primal feasibility or objective audit failed")
        return result
