from ..models import RiskResult

class CountryRiskCalculator:
    @staticmethod
    def calculate(spread: float, volatility: float) -> float:
        return spread*volatility

class GeopoliticalRiskCalculator:
    @staticmethod
    def calculate(base: float,gamma: float,index: float,mean: float,sigma: float) -> float:
        if sigma<=0: raise ValueError('IGPR sigma must be positive')
        return base+gamma*max(0.,(index-mean)/sigma)

    @staticmethod
    def rates(project,country) -> RiskResult:
        crp=CountryRiskCalculator.calculate(country.spread,country.volatility)
        gpr=GeopoliticalRiskCalculator.calculate(country.gpr_base,country.gamma,country.igpr,project.igpr_mean,project.igpr_sigma)
        rate=project.wacc+crp+gpr
        if rate<=-1: raise ValueError('Discount rate must exceed -1')
        return RiskResult(crp,gpr,rate)
