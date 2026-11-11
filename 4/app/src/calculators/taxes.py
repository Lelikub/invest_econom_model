class FiscalTaxCalculator:
    @staticmethod
    def literal_pdf(ebit: float,nominal: float,holiday: float,credit: float,floor: float) -> float:
        return max(ebit*min(nominal,holiday)-credit,ebit*floor)

    @staticmethod
    def cash_tax(ebit: float,nominal: float,holiday: float,credit: float,floor: float) -> float:
        return max(0.,FiscalTaxCalculator.literal_pdf(ebit,nominal,holiday,credit,floor))
