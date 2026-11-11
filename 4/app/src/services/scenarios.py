from dataclasses import replace
from ..models import ScenarioResult
from ..calculators.scenario_statistics import ScenarioAggregationCalculator
from .finance import CrossBorderSupplyChainEvaluator

class ScenarioService:
    def stress(self,inputs):
        s=inputs.scenarios; e=CrossBorderSupplyChainEvaluator()
        return {
            'STRESS1':e.evaluate(inputs.project,replace(inputs.countries['VNM'],igpr=s['vnm_igpr'],logistics_in=s['vnm_freight'],lead_days=s['vnm_days'])),
            'STRESS2':e.evaluate(inputs.project,replace(inputs.countries['SRB'],cbam=s['srb_cbam']))}

    def run(self,inputs) -> ScenarioResult:
        s=inputs.scenarios; e=CrossBorderSupplyChainEvaluator(); results={}
        def country(c,scenario):
            if scenario=='A': return replace(c,igpr=c.igpr*(1-s['integration_reduction']),equip_duty=0,input_duty=0,cbam=0)
            if scenario=='ZERO': return replace(c,spread=0,gpr_base=0,gamma=0,equip_duty=0,input_duty=0,cbam=0,logistics_in=0,logistics_out=0)
            if scenario=='PILLAR2' and c.code=='VNM': return replace(c,holiday_tax=0,holiday_end=c.first+3)
            if scenario in ('C','STRESS1') and c.code=='VNM': return replace(c,igpr=s['vnm_igpr'],logistics_in=s['vnm_freight'],lead_days=s['vnm_days'])
            if scenario in ('C','STRESS2') and c.code=='SRB': return replace(c,cbam=s['srb_cbam'])
            if scenario=='C' and c.code=='DEU': return replace(c,igpr=c.igpr*(1+s['deu_igpr_increase']),inflation=s['deu_inflation'])
            return c
        for scenario in ('A','B','C','ZERO','PILLAR2','STRESS1','STRESS2'):
            results[scenario]={code:e.evaluate(inputs.project,country(c,scenario)) for code,c in inputs.countries.items()}
        probabilities={k:s['p_'+k] for k in 'ABC'}
        stats={code:ScenarioAggregationCalculator.calculate([results[k][code].parent.npv for k in 'ABC'],list(probabilities.values())) for code in inputs.countries}
        return ScenarioResult(results,stats,probabilities)
