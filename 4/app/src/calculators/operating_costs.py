from ..models import SupplyResult

class TariffAndLogisticsCalculator:
    @staticmethod
    def calculate(project,country) -> SupplyResult:
        weighted=country.share_eu*project.price_eu+country.share_asia*project.price_asia
        inbound=country.raw_base*country.logistics_in
        duty=country.raw_base*country.input_duty
        outbound=weighted*country.logistics_out
        cbam=country.share_eu*project.price_eu*country.cbam
        return SupplyResult(weighted,country.raw_base+inbound+duty,weighted-outbound-cbam,cbam,inbound,duty,outbound)
