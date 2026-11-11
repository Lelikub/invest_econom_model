from ..models import AnnualResult
from .capex import DepreciationCalculator
from .taxes import FiscalTaxCalculator

class WithholdingTaxCalculator:
    @staticmethod
    def parent_cashflow_economic_rule(operating: float,nwc_effect: float,investment: float,wht: float) -> float:
        """Assume payout=100% of positive operating cash; no WHT on capital."""
        return investment+nwc_effect+operating-max(operating,0)*wht

    @staticmethod
    def parent_cashflow_literal_pdf(fcff: float,nwc_change: float,wht: float) -> float:
        """NON_AUTHORITATIVE: exact page 13 typography, WHT multiplies ΔNWC."""
        return fcff-nwc_change*(1-wht) if fcff<=0 else fcff-nwc_change

class CashFlowCalculator:
    @staticmethod
    def calculate(project,country,capex,supply,risk) -> tuple[AnnualResult,...]:
        rows=[]; cumulative=0.
        for t in range(int(project.calendar_end)+1):
            load=0. if t<country.first or t>country.last else (country.first_load if t==country.first else country.last_load if t==country.last else 1.)
            volume=project.volume*load
            eu=volume*country.share_eu*project.price_eu; asia=volume*country.share_asia*project.price_asia
            outbound=volume*supply.outbound_unit; cbam=volume*supply.cbam_unit
            revenue=eu+asia-outbound-cbam
            raw=volume*country.raw_base; inbound=volume*supply.inbound_unit; duty=volume*supply.duty_unit
            fixed=project.fixed_opex*load; opex=raw+inbound+duty+fixed
            depreciation=DepreciationCalculator.calculate(capex.net,project.years,load)
            ebit=revenue-opex-depreciation
            holiday=country.holiday_tax if t<=country.holiday_end else country.nominal_tax
            credit=country.tax_credit*load
            gross=ebit*min(country.nominal_tax,holiday)-credit
            literal_tax=FiscalTaxCalculator.literal_pdf(ebit,country.nominal_tax,holiday,credit,project.pillar_floor)
            tax=FiscalTaxCalculator.cash_tax(ebit,country.nominal_tax,holiday,credit,project.pillar_floor)
            operating=ebit-tax+depreciation
            change=project.nwc if t==country.nwc_draw else -project.nwc if t==country.nwc_release else 0.
            investment=-capex.net if t==0 else 0.
            local=investment+operating-change
            wht=max(operating,0)*country.wht
            parent=WithholdingTaxCalculator.parent_cashflow_economic_rule(operating,-change,investment,country.wht)
            literal=WithholdingTaxCalculator.parent_cashflow_literal_pdf(local,change,country.wht)
            tax_operating=ebit-literal_tax+depreciation
            tax_parent=WithholdingTaxCalculator.parent_cashflow_economic_rule(tax_operating,-change,investment,country.wht)
            discount=1/(1+risk.rate)**t; discounted=parent*discount; cumulative+=discounted
            rows.append(AnnualResult(t,load,volume,eu,asia,outbound,cbam,revenue,raw,inbound,duty,fixed,opex,depreciation,
                ebit,holiday,credit,gross,literal_tax,tax,operating,change,-change,investment,local,wht,parent,literal,tax_parent,discount,discounted,cumulative))
        return tuple(rows)
