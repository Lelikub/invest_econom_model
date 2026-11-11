from ..models import CapexResult

class CAPEXAndSubsidyCalculator:
    @staticmethod
    def calculate(project,country) -> CapexResult:
        gross=project.capex_base*(1+country.inflation)*(1+country.equip_duty*(1-country.duty_free))
        subsidy=gross*country.subsidy_rate*country.approval*(1-country.clawback)/(1+country.gov_rate)**country.subsidy_year
        return CapexResult(gross,subsidy,gross-subsidy)

class DepreciationCalculator:
    @staticmethod
    def calculate(net_capex: float,years: float,load: float) -> float:
        return net_capex/years*load
