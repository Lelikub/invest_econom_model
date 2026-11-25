from dataclasses import replace
from fractions import Fraction
from itertools import combinations
import math

from ..calculators.operations import TOL
from ..repositories import normalize


def ids(result):
    return "+".join(map(str,result.ids)) or "∅"


def portfolio_row(result, **label):
    return dict(**label, ids=ids(result), capex=result.capex, npv=result.npv, score=result.score,
                budget_slack=result.slack, status=result.status, upper_bound=result.bound, mip_gap=result.gap)


class ParetoAnalysis:
    def __init__(self, optimizer):
        self.optimizer = optimizer

    @staticmethod
    def frontier(feasible):
        ordered = sorted(feasible,key=lambda p:(-p.score,-p.npv,p.capex,p.ids))
        frontier = []
        best = -math.inf
        for option in ordered:
            if option.npv > best:
                frontier.append(option)
                best = option.npv
        return list(reversed(frontier))

    @staticmethod
    def weighted(feasible, frontier):
        pairs = [(Fraction(str(p.npv)), Fraction(p.score)) for p in feasible]
        n0,s0 = map(min,zip(*pairs))
        n1,s1 = map(max,zip(*pairs))
        normalized = [((n-n0)/(n1-n0 or 1),(s-s0)/(s1-s0 or 1)) for n,s in pairs]
        points = {(p.npv,p.score) for p in frontier}
        # All intersections of normalized Pareto objectives partition [0,1].
        # Exact rational comparisons include ties at transition weights.
        cuts = {Fraction(0),Fraction(1)}
        for (a,b),(c,d) in combinations(sorted({xy for p,xy in zip(feasible,normalized) if (p.npv,p.score) in points}),2):
            slope = (a-b)-(c-d)
            if slope and 0 < (d-b)/slope < 1:
                cuts.add((d-b)/slope)
        boundaries = sorted(cuts)
        probes = cuts | {(a+b)/2 for a,b in zip(boundaries,boundaries[1:])} | {Fraction(i,100) for i in range(101)}
        rows = []
        supported = set()
        for alpha in sorted(probes):
            values = [alpha*n + (1-alpha)*s for n,s in normalized]
            optimum = max(values)
            for p,value in zip(feasible,values):
                if value != optimum:
                    continue
                is_front = (p.npv,p.score) in points
                if is_front:
                    supported.add((p.npv,p.score))
                rows.append(portfolio_row(p,alpha=float(alpha),alpha_exact=str(alpha),weighted_objective=float(value),
                                          on_frontier=is_front, probe="breakpoint" if alpha in cuts else "sample"))
        return rows,supported, (float(n0),float(n1),int(s0),int(s1))

    @staticmethod
    def mrt_and_knee(frontier, limit):
        segments = [
            {"from_ids":ids(a), "to_ids":ids(b), "from_score":a.score, "to_score":b.score,
             "from_npv":a.npv, "to_npv":b.npv, "score_gain":b.score-a.score, "npv_loss":a.npv-b.npv,
             "mrt":abs((b.npv-a.npv)/(b.score-a.score)), "efficient":abs((b.npv-a.npv)/(b.score-a.score)) < limit}
            for a,b in zip(frontier,frontier[1:]) if b.score>a.score]
        if len(frontier)<3:
            return segments, [{"status":"NO_STABLE_KNEE","reason":"Fewer than three frontier points"}]
        left,right = frontier[0],frontier[-1]
        dp = left.npv-right.npv
        ds = right.score-left.score
        scales = (0.8,1.0,1.25)
        angles = {}
        for scale in scales:
            xy = [((p.score-left.score)/ds, scale*(p.npv-right.npv)/dp) for p in frontier]
            directions = [math.atan2(b[1]-a[1],b[0]-a[0]) for a,b in zip(xy,xy[1:])]
            angles[scale] = [abs(math.degrees(b-a)) for a,b in zip(directions,directions[1:])]
        winners = [max(range(len(angles[s])),key=angles[s].__getitem__) for s in scales]
        ordered = [sorted(angles[s],reverse=True) for s in scales]
        stable = len(set(winners)) == 1 and all(a[0]>1 and (len(a)==1 or a[0]-a[1]>1e-7) for a in ordered)
        rows=[]
        for i,p in enumerate(frontier[1:-1]):
            rows.append(portfolio_row(p, angle_080=angles[.8][i],angle_100=angles[1.0][i],angle_125=angles[1.25][i],
                                      criterion="unique maximum above 1°, same point at scales 0.8,1,1.25",
                                      knee_status="KNEE" if stable and i == winners[1] else ("OTHER" if stable else "NO_STABLE_KNEE")))
        return segments, rows

    def run(self, inputs, step=10, mrt_limit=.5):
        feasible,count = self.optimizer.enumerate(inputs)
        frontier = self.frontier(feasible)
        low,high = min(p.score for p in feasible),max(p.score for p in feasible)
        grid = sorted(set(range(low,high+1,step)) | {high})
        epsilon = []
        epsilon_points = set()
        for e in grid:
            solved = self.optimizer.solve(inputs,e)
            options = [p for p in feasible if p.score>=e]
            best = max(options,key=lambda p:(p.npv,p.score,-p.capex))
            if solved.status!="OPTIMAL" or abs(solved.npv-best.npv)>TOL:
                raise RuntimeError(f"Epsilon {e} disagrees with enumeration")
            # Canonicalize equal-NPV ties toward the highest score without changing the MILP objective.
            epsilon_points.add((best.npv,best.score))
            epsilon.append(portfolio_row(replace(best,status=solved.status,bound=solved.bound,gap=solved.gap),
                                         epsilon=e, raw_milp_ids=ids(solved),tiebreak="max MCDA at optimal NPV"))
        weighted,supported,ranges = self.weighted(feasible,frontier)
        mrt,knee = self.mrt_and_knee(frontier,mrt_limit)
        return dict(feasible=feasible, examined=count, frontier=frontier, epsilon=epsilon, epsilon_points=epsilon_points,
                    weighted=weighted, supported=supported, ranges=ranges,mrt=mrt,knee=knee)


class ScenarioAnalysis:
    def __init__(self, optimizer):
        self.optimizer = optimizer

    def edges(self, op, pf, sc, base):
        opt = self.optimizer
        nmp = replace(op, materials=(replace(op.materials[0],capacity=sc.zero_nmp),op.materials[1]))
        negative = replace(op, products=(replace(op.products[0],margin=sc.negative_margin),*op.products[1:]))
        r1 = opt.solve_operational_milp(nmp)
        r2 = opt.solve_operational_milp(negative)
        f2 = opt.extract_fixed_lp_duals(negative,r2.y)
        r3 = opt.solve_operational_milp(op,forbidden=(sc.forbidden_machine,))
        excluded = replace(pf,links=pf.links+(sc.extra_link,))
        r4 = opt.solve_portfolio_knapsack(excluded)
        return [
            dict(case="Нулевой NMP",status=r1.status,objective=r1.objective,x1=r1.x[0],x2=r1.x[1],x3=r1.x[2],
                 rc1=None,ids=None,profit_loss=base.objective-r1.objective,nmp_load=r1.load[3],m1_load=r1.load[0],m2_load=r1.load[1]),
            dict(case="Маржа Э-1 < 0",status=r2.status,objective=r2.objective,x1=r2.x[0],x2=r2.x[1],x3=r2.x[2],
                 rc1=f2.reduced[0],ids=None,profit_loss=base.objective-r2.objective,nmp_load=r2.load[3],m1_load=r2.load[0],m2_load=r2.load[1]),
            dict(case="Агрегат 3 выключен",status=r3.status,objective=r3.objective,x1=r3.x[0],x2=r3.x[1],x3=r3.x[2],
                 rc1=None,ids=None,profit_loss=base.objective-r3.objective,nmp_load=r3.load[3],m1_load=r3.load[0],m2_load=r3.load[1]),
            dict(case="Проекты 1 и 4 исключают друг друга",status=r4.status,objective=None,x1=None,x2=None,x3=None,
                 rc1=None,ids=ids(r4),portfolio_npv=r4.npv,profit_loss=None,nmp_load=None,m1_load=None,m2_load=None),
        ]

    def stress(self, op, pf, sc, base, exact):
        finance_inputs = replace(pf,budget=sc.stress_budget,
                                 projects=tuple(replace(p,npv=p.npv*(1-sc.npv_cut)) for p in pf.projects))
        finance = self.optimizer.solve_portfolio_knapsack(finance_inputs)
        green = self.optimizer.solve_portfolio_knapsack(pf,score_floor=sc.score_floor)
        for data,result,floor in ((finance_inputs,finance,None),(pf,green,sc.score_floor)):
            feasible,_ = self.optimizer.portfolio.enumerate(data)
            values = [p.npv for p in feasible if floor is None or p.score>=floor]
            if (not values and result.status!="INFEASIBLE") or (values and (
                    result.status!="OPTIMAL" or abs(result.npv-max(values))>TOL)):
                raise RuntimeError("Stress portfolio MILP disagrees with enumeration")
        tax = normalize(sc.carbon_tax,"руб.","тыс. руб.") * sc.emission_factor
        deltas = [tax*(1/p.yield_rate-1) for p in op.products]
        carbon_inputs = replace(op,products=tuple(replace(p,margin=p.margin-d) for p,d in zip(op.products,deltas)))
        carbon = self.optimizer.solve_operational_milp(carbon_inputs)
        cert = self.optimizer.operations.enumerate_modes(carbon_inputs)
        if abs(carbon.objective-cert.objective)>TOL:
            raise RuntimeError("Carbon production MILP disagrees with enumeration")
        carbon_rows=[]
        for p, d, x0, x1 in zip(op.products,deltas,base.x,carbon.x):
            waste0,waste1 = x0*(1/p.yield_rate-1),x1*(1/p.yield_rate-1)
            carbon_rows.append(dict(product=p.code,base_output=x0,carbon_output=x1,base_waste=waste0,carbon_waste=waste1,
                                    original_margin=p.margin,delta_margin=d,carbon_margin=p.margin-d,
                                    emissions=waste1*sc.emission_factor,tax_paid=waste1*tax))
        return dict(finance=finance,green=green,carbon=carbon,carbon_rows=carbon_rows,
                    finance_inputs=finance_inputs, carbon_inputs=carbon_inputs,
                    carbon_profit_loss=base.objective-carbon.objective,
                    green_npv_loss=exact.npv-green.npv if green.status=="OPTIMAL" else None)
