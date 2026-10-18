from ..models import WaterfallResult
from .finance import finite


class CovenantService:
    @staticmethod
    def locked(dscr,covenant):
        finite(dscr,covenant)
        return dscr<covenant


class CashWaterfallCalculator:
    @staticmethod
    def calculate(revenue,opex,taxes,debt_service,dscr,covenant,literal=False,dsra_target=None):
        finite(revenue,opex,taxes,debt_service,dscr,covenant)
        if min(revenue,opex,taxes,debt_service)<0: raise ValueError('Negative waterfall input')
        locked=CovenantService.locked(dscr,covenant)
        cfads=revenue-opex-taxes
        paid=0. if literal and locked else min(max(cfads,0),debt_service)
        cash_after=cfads-paid
        available=max(cash_after,0)
        if dsra_target is not None and dsra_target<0: raise ValueError('Negative DSRA target')
        dsra=available if locked else min(available,dsra_target or 0)
        dividends=0. if locked else available-dsra
        retained=cash_after-dsra-dividends
        flows=[dict(label='Выручка',amount=revenue),dict(label='OPEX',amount=-opex),
            dict(label='Налоги (допущение)',amount=-taxes),dict(label='Долг',amount=-paid),
            dict(label='DSRA (сценарий)',amount=-dsra),dict(label='Дивиденды',amount=-dividends)]
        return WaterfallResult('literal_pdf' if literal else 'illustrative_consistent',locked,
            debt_service,paid,cfads,cash_after,dsra,dividends,retained,
            max(debt_service-paid,0),flows)
