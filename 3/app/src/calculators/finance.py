"""Pure scalar finance calculators. Rates are fractions, never percent points."""
import math


def finite(*values):
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite financial input')


def fraction(value):
    finite(value)
    if not 0<=value<=1:
        raise ValueError('Fraction must be in [0,1]')


class EffectiveTaxCalculator:
    @staticmethod
    def calculate(nominal,relief,floor):
        for v in (nominal,relief,floor): fraction(v)
        return max(nominal-relief,floor)


class LeverageCalculator:
    @staticmethod
    def calculate(debt,equity):
        finite(debt,equity)
        if debt<0 or equity<=0: raise ValueError('Require D>=0, E>0')
        return debt/equity


class HamadaBetaCalculator:
    @staticmethod
    def unlever(beta,tax,de):
        fraction(tax); finite(beta,de)
        if de<0: raise ValueError('Negative leverage')
        return beta/(1+(1-tax)*de)

    @staticmethod
    def relever(beta,tax,de):
        fraction(tax); finite(beta,de)
        if de<0: raise ValueError('Negative leverage')
        return beta*(1+(1-tax)*de)


class CAPMCalculator:
    @staticmethod
    def calculate(rf,beta,erp,crp):
        finite(rf,beta,erp,crp)
        return rf+beta*erp+crp


class CostOfDebtCalculator:
    @staticmethod
    def calculate(rf,*spreads):
        finite(rf,*spreads)
        return rf+sum(spreads)

    @staticmethod
    def after_tax(kd,tax):
        finite(kd); fraction(tax)
        return kd*(1-tax)


class WACCCalculator:
    @staticmethod
    def calculate(we,wd,ke,kd_after_tax):
        fraction(we); fraction(wd); finite(ke,kd_after_tax)
        if not math.isclose(we+wd,1,abs_tol=1e-12): raise ValueError('Weights must sum to one')
        return we*ke+wd*kd_after_tax


class MissingDefaultParameters(ValueError):
    pass


class CreditSpreadCalculator:
    @staticmethod
    def calculate(dscr,covenant,gamma1,gamma2=None,default_spread=None,penalty=None):
        finite(dscr,covenant,gamma1)
        if dscr<0 or covenant<1 or gamma1<0: raise ValueError('Invalid covenant parameters')
        if dscr>=covenant: return 0.
        if dscr>=1: return gamma1*(covenant/dscr-1)
        if any(v is None for v in (gamma2,default_spread,penalty)):
            raise MissingDefaultParameters('DSCR<1: gamma2, DefaultSpread, Penalty отсутствуют')
        finite(gamma2,default_spread,penalty)
        if min(gamma2,default_spread,penalty)<0: raise ValueError('Negative default input')
        return gamma2*default_spread+penalty


class DSCRCalculator:
    @staticmethod
    def calculate(dscr0,mu):
        finite(dscr0); fraction(mu)
        if dscr0<=0: raise ValueError('Positive baseline DSCR required')
        return dscr0*(1-mu)


class DiscountEffectCalculator:
    @staticmethod
    def calculate(wacc,year):
        finite(wacc,year)
        if wacc<=-1 or year<0: raise ValueError('Invalid discount horizon/rate')
        return (1+wacc)**(-year)
