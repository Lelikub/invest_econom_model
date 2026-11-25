from dataclasses import dataclass
from itertools import product
import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from ..models import OperationResult
from ..services.inputs import DataValidationService

TOL = 1e-6


def check_mip(result, objective, gap_limit):
    bound = -float(result.mip_dual_bound)
    reported = float(result.mip_gap)
    difference = bound-objective
    gap = max(0.0, difference) / abs(objective) if abs(objective) > TOL else (0.0 if abs(difference) <= TOL else math.inf)
    if result.status != 0 or not result.success or not all(map(math.isfinite, (bound, reported, gap))):
        raise RuntimeError(f"MIP certificate invalid: {result.message}")
    if difference < -TOL or max(gap, reported) > gap_limit + 1e-10:
        raise RuntimeError(f"MIP certificate disagreement: {objective=}, {bound=}, {gap=}, {reported=}")
    return bound, reported


@dataclass(frozen=True)
class OperatingModel:
    matrix: np.ndarray
    capacity: np.ndarray
    fixed_cost: np.ndarray
    margin: np.ndarray
    yields: np.ndarray

    @property
    def augmented(self):
        launch = np.vstack((-np.diag(self.capacity[:3]), np.zeros((2,3))))
        return np.hstack((self.matrix, launch))

    @property
    def rhs(self):
        return np.r_[np.zeros(3), self.capacity[3:]]

    @property
    def objective_vector(self):
        return np.r_[self.margin, -self.fixed_cost]


class OperationsOptimizer:
    def __init__(self, gap_limit=1e-4):
        self.gap_limit = gap_limit

    @staticmethod
    def model(inputs):
        DataValidationService().validate_operations(inputs)
        yields = np.array([p.yield_rate for p in inputs.products])
        return OperatingModel(
            np.asarray(inputs.machine_coefficients + inputs.material_coefficients) / yields,
            np.array([r.capacity for r in (*inputs.machines, *inputs.materials)]),
            np.array([m.fixed_cost for m in inputs.machines]),
            np.array([p.margin for p in inputs.products]), yields)

    @staticmethod
    def result(model, x, y, solver_objective, **kwargs):
        load = model.matrix @ x
        rhs = model.capacity * np.r_[y, [1,1]]
        slack = rhs - load
        objective = float(model.margin @ x - model.fixed_cost @ y)
        if (not np.isfinite(np.r_[x,y,load,slack,objective]).all() or min(x) < -TOL
                or min(y) < -TOL or max(y) > 1+TOL or min(slack) < -TOL
                or abs(objective-solver_objective) > TOL):
            raise RuntimeError("Production primal feasibility or objective audit failed")
        return OperationResult("OPTIMAL", tuple(map(float,x)), tuple(map(float,y)), objective,
                               tuple(map(float,load)), tuple(map(float,rhs)), tuple(map(float,slack)), **kwargs)

    def relaxation(self, inputs):
        model = self.model(inputs)
        r = linprog(-model.objective_vector, A_ub=model.augmented, b_ub=model.rhs,
                    bounds=[(0,None)]*3+[(0,1)]*3, method="highs-ds")
        if not r.success:
            raise RuntimeError(r.message)
        shadow = -r.ineqlin.marginals
        upper = -r.upper.marginals[3:]
        reduced = model.objective_vector - model.augmented.T @ shadow - np.r_[np.zeros(3),upper]
        solved = self.result(model, r.x[:3], r.x[3:], -r.fun, shadow=tuple(shadow),
                             reduced=tuple(reduced[:3]), upper_shadow=tuple(upper), launch_reduced=tuple(reduced[3:]))
        self.audit_lp(solved, reduced, r.x, shadow @ model.rhs + upper.sum(), upper)
        return solved

    def milp(self, inputs, forbidden=()):
        model = self.model(inputs)
        if any(i not in (1,2,3) for i in forbidden):
            raise ValueError("Invalid forbidden machine ID")
        upper = np.r_[[np.inf]*3, [0 if i in forbidden else 1 for i in (1,2,3)]]
        r = milp(-model.objective_vector, integrality=[0]*3+[1]*3, bounds=Bounds(np.zeros(6),upper),
                 constraints=LinearConstraint(model.augmented, -np.inf, model.rhs),
                 options={"mip_rel_gap": self.gap_limit})
        if not r.success or r.x is None:
            raise RuntimeError(r.message)
        y = np.rint(r.x[3:])
        if np.max(np.abs(y-r.x[3:])) > TOL or np.any(y > upper[3:]):
            raise RuntimeError("Production binary or forbidden bounds audit failed")
        bound, gap = check_mip(r, -r.fun, self.gap_limit)
        return self.result(model, r.x[:3], y, -r.fun, bound=bound, gap=gap)

    def fixed(self, inputs, y):
        model = self.model(inputs)
        if len(y) != 3 or any(i not in (0,1) for i in y):
            raise ValueError("Fixed LP requires three binary launch values")
        rhs = model.capacity * np.r_[y,[1,1]]
        r = linprog(-model.margin, A_ub=model.matrix, b_ub=rhs, method="highs-ds")
        if not r.success:
            raise RuntimeError(r.message)
        shadow = -r.ineqlin.marginals
        reduced = model.margin - model.matrix.T @ shadow
        fixed_cost = model.fixed_cost @ y
        solved = self.result(model, r.x, y, -r.fun-fixed_cost, shadow=tuple(shadow), reduced=tuple(reduced))
        self.audit_lp(solved, reduced, r.x, shadow @ rhs-fixed_cost)
        return solved

    @staticmethod
    def audit_lp(result, reduced, primal, dual_objective, upper=()):
        if (min(result.shadow) < -TOL or max(reduced) > TOL or not np.allclose(
                np.asarray(result.shadow)*result.slack, 0, atol=TOL)
                or not np.allclose(reduced*primal, 0, atol=TOL)
                or abs(result.objective-dual_objective) > TOL):
            raise RuntimeError("LP dual feasibility, strong duality or complementarity audit failed")
        if len(upper) and (min(upper) < -TOL or not np.allclose(upper*(1-np.asarray(result.y)), 0, atol=TOL)):
            raise RuntimeError("LP upper-bound complementarity audit failed")

    def enumerate_modes(self, inputs, forbidden=()):
        return max((self.fixed(inputs, y) for y in product((0,1),repeat=3)
                    if all(y[i-1] == 0 for i in forbidden)), key=lambda r: r.objective)
