import math
from ..models import StatisticsResult

class ScenarioAggregationCalculator:
    @staticmethod
    def calculate(values,probabilities) -> StatisticsResult:
        if len(values)!=len(probabilities) or not values or not all(math.isfinite(x) for x in [*values,*probabilities]) or any(p<0 for p in probabilities) or not math.isclose(sum(probabilities),1,abs_tol=1e-12):
            raise ValueError('Invalid discrete scenario probabilities')
        expected=sum(p*v for p,v in zip(probabilities,values))
        variance=sum(p*(v-expected)**2 for p,v in zip(probabilities,values))
        return StatisticsResult(expected,variance,math.sqrt(variance),sum(p for p,v in zip(probabilities,values) if v<0))
