from .operations import OperationsOptimizer
from .portfolio import PortfolioOptimizer


class ProductionAndPortfolioOptimizer:
    def __init__(self, gap_limit=1e-4):
        self.operations = OperationsOptimizer(gap_limit)
        self.portfolio = PortfolioOptimizer(gap_limit)

    def solve_operational_milp(self, inputs, forbidden=()):
        return self.operations.milp(inputs, forbidden)

    def extract_fixed_lp_duals(self, inputs, y):
        return self.operations.fixed(inputs, y)

    def solve_portfolio_knapsack(self, inputs, score_floor=None):
        return self.portfolio.solve(inputs, score_floor)
