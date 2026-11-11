from ..models import CountryResult
from ..calculators.country_risk import GeopoliticalRiskCalculator
from ..calculators.capex import CAPEXAndSubsidyCalculator
from ..calculators.operating_costs import TariffAndLogisticsCalculator
from ..calculators.cash_flows import CashFlowCalculator
from ..calculators.financial_metrics import FinancialMetricsCalculator

class CrossBorderSupplyChainEvaluator:
    def evaluate(self,project,country) -> CountryResult:
        risk=GeopoliticalRiskCalculator.rates(project,country)
        capex=CAPEXAndSubsidyCalculator.calculate(project,country)
        supply=TariffAndLogisticsCalculator.calculate(project,country)
        annual=CashFlowCalculator.calculate(project,country,capex,supply,risk)
        metrics=[FinancialMetricsCalculator.calculate([getattr(a,key) for a in annual],risk.rate)
            for key in ('local_cf','parent_cf','parent_literal','parent_literal_tax')]
        return CountryResult(country,risk,capex,supply,annual,*metrics)

FinancialModelService=CrossBorderSupplyChainEvaluator
