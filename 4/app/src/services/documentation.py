"""Source conflicts and formula/requirement registry; educational assumptions."""
from ..io_utils import write_json, write_csv

SOURCE_ISSUES=[
    dict(id='SRC_NWC',page='8,13',issue='Стр.8 ΔNWC назван оттоком −4 млн; стр.13 ΔNWC вычитается из FCFF.',decision='NWC_change=+4 млн при вложении, −4 млн при возврате; cash_effect=−change. Ни CAPEX, ни NWC не облагаются WHT.',status='SOURCE_CONFLICT',test='test_calendar; test_identities'),
    dict(id='SRC_WHT',page='13',issue='Текст требует WHT с положительного операционного CF; печатная ветвь: FCFF−ΔNWC*(1−WHT) при FCFF≤0, FCFF−ΔNWC при FCFF>0.',decision='Основной economic_rule; буквальный literal_pdf NON_AUTHORITATIVE сохранен точно по визуально проверенной типографике. Не добавлены отсутствующие скобки вокруг FCFF−ΔNWC.',status='SOURCE_CONFLICT',test='test_wht; test_literal_pdf_exact_typography'),
    dict(id='SRC_NEG_TAX',page='13',issue='max(CIT_gross, EBIT*floor) при EBIT<0 может создавать налоговый возврат.',decision='Основной cash_tax=max(0,literal_tax), без переноса убытков. Буквальная формула сохранена отдельно; численный эффект публикуется.',status='SOURCE_ISSUE',test='test_cash_tax'),
    dict(id='SRC_VNM_TAX',page='5,14',issue='База VNM 15% t3–11,20% t12–13; edge case требует 0%→15% в первые 4 года.',decision='Базовый календарь сохраняется; отдельная фикстура PILLAR2 задает 0% t3–6 и проверяет пол при положительном EBIT.',status='SOURCE_ISSUE',test='test_tax_calendar_and_credit; test_scenarios'),
    dict(id='SRC_SRB_IP',page='5,14',issue='3% IP Box относится к роялти, которых у проекта нет.',decision='Налог SRB 15% в базе и стрессе; отмена IP Box не создает искусственного налогового эффекта.',status='SOURCE_ISSUE',test='test_scenarios'),
    dict(id='SRC_EXPORT',page='2,10',issue='На стр.2 указано 85% экспорта; таблица2 задает полное распределение продукции по рынкам ЕС/Азии.',decision='Для денежной модели приоритет конкретной матрице рынков. Отдельный неназванный внутренний рынок 15% не добавляется.',status='SOURCE_ISSUE',test='test_pdf_controls'),
    dict(id='SRC_DEU_CIT',page='5',issue='29.80% в строке DEU отличается от суммы перечисленных компонентов 15+0.825+14=29.825%.',decision='Применяется явно заданная сводная ставка 29.80%; компоненты остаются в оригинальном тексте CSV.',status='SOURCE_ISSUE',test='test_pdf_controls'),
    dict(id='SRC_SUBSIDY_TIME',page='7,8,12',issue='DEU субсидия t4 описана как через год после ввода t3; первый полный CF по календарю t4.',decision='Не смешивать ввод в конце t3 с потоком t4; t_subsidy=4 считывается отдельно, субсидия учтена только в CF0 через PV.',status='SOURCE_ISSUE',test='test_capex_exemption_and_advance'),
]

FORMULAS=[
 ('RISK_CRP','spread × volatility','Доли ставки; volatility безразмерна','12','3','CountryRiskCalculator','test_pdf_controls','risk_rates.csv'),
 ('RISK_GPR','base + gamma × max(0,(IGPR−mean)/sigma)','gamma из п.п./σ переводится в долю/σ','12','7','GeopoliticalRiskCalculator','test_monotonic_risk','risk_rates.csv'),
 ('RISK_RATE','WACC + CRP + GPR','Годовая ставка, r>−1','12','4','GeopoliticalRiskCalculator','test_identities','risk_rates.csv'),
 ('CAPEX_GROSS','CAPEX_base(1+inflation)(1+equip_duty(1−duty_free))','USD t0','12','22,24','CAPEXAndSubsidyCalculator','test_capex_exemption_and_advance','capex.csv'),
 ('SUBSIDY_PV','gross × alpha × Papproval × (1−Pclawback)/(1+rgov)^tsub','Ожидаемая PV, USD, не гарантированный грант','12','21,22,24','CAPEXAndSubsidyCalculator','test_no_subsidy_boundary','capex.csv'),
 ('CAPEX_NET','gross−subsidy_PV; CF0=−net','USD; субсидия второй раз не поступает','8,12','24','CAPEXAndSubsidyCalculator','test_identities','capex.csv'),
 ('SUPPLY_PRICE','shareEU PriceEU + shareAsia PriceAsia','USD/m²','9–12','23','TariffAndLogisticsCalculator','test_pdf_controls','supply_chains.csv'),
 ('REVENUE','Volume × [weighted(1−out)−shareEU PriceEU CBAM]','USD/year; CBAM только с контрактных отгрузок в ЕС','12','23','TariffAndLogisticsCalculator','test_cbam_and_double_count','annual_cashflows.csv'),
 ('OPEX','Volume × raw(1+input_duty+in)+fixed × load','USD/year; пошлина и логистика аддитивны','12','23','TariffAndLogisticsCalculator','test_cbam_and_double_count','annual_cashflows.csv'),
 ('DEPRECIATION','netCAPEX / N × load','USD/year; сумма D&A=netCAPEX','2,8','23 (D&A), база уточнена заданием','DepreciationCalculator','test_calendar','annual_cashflows.csv'),
 ('CIT','max(0,max(EBIT min(nominal,holiday)−credit,EBIT floor))','USD/year; без cash refund. Буквальная версия без max(0,…)','5,13','17,21,23,25','FiscalTaxCalculator','test_cash_tax','taxation.csv'),
 ('FCFF','investment + EBIT−cashTax+D&A−NWC_change','USD/calendar year; NWC положителен при вложении','8,13','23','CashFlowCalculator','test_identities','annual_cashflows.csv'),
 ('WHT_ECONOMIC','investment+NWC_effect+operating−max(0,operating)WHT','USD; payout=100% положительного operating CF','13','25–26 (контуры WHT); приоритет заданию','WithholdingTaxCalculator','test_wht','source_sensitivity.csv'),
 ('WHT_LITERAL','IF(FCFF≤0,FCFF−NWC_change(1−WHT),FCFF−NWC_change)','Точная запись PDF; SOURCE_CONFLICT/NON_AUTHORITATIVE','13','Не эквивалентна текстовому принципу','WithholdingTaxCalculator','test_literal_pdf_exact_typography','source_sensitivity.csv'),
 ('NPV','Σ CFt/(1+r)^t; TV=0','USD; календарь t=0…T','13','5 (DCF пример); явная календарная сумма — определение модели','FinancialMetricsCalculator','test_metrics_roots_and_payback','base_metrics.csv'),
 ('IRR','Все вещественные корни Σ CFt xt=0, x>0; IRR=1/x−1','Доля/год; UNIQUE/NO_ROOT/MULTIPLE_ROOTS','13 (требование метрики)','Отдельная формула IRR в лекции не найдена; численный метод документирован','FinancialMetricsCalculator','test_metrics_roots_and_payback','base_metrics.csv'),
 ('PI','PV положительных CF / |PV отрицательных CF|','Безразмерно; включает поздний NWC отток','13 (требование метрики)','Определение выбрано моделью, точный слайд не заявляется','FinancialMetricsCalculator','test_pi_includes_nwc','base_metrics.csv'),
 ('DPP','(t−1)−CumPV(t−1)/PV(t) при первом CumPV≥0','Календарные годы; интерполяция внутри года, NOT_REACHED','13 (требование метрики)','Определение интерполяции принято моделью','FinancialMetricsCalculator','test_metrics_roots_and_payback','base_metrics.csv'),
 ('SCENARIO','E=Σ pNPV; Var=Σp(NPV−E)²; σ=√Var','USD; USD²; USD. Дискретные сценарии, не Monte Carlo','14–15','Метод дискретного ожидания; точный слайд не заявляется','ScenarioAggregationCalculator','test_statistical_probabilities','scenario_statistics.csv'),
]

class DocumentationService:
    def write(self,docs):
        docs.mkdir(parents=True,exist_ok=True)
        header='# Реестр формул\n\nGRP из задания обозначается CRP. Учебные фискальные условия не являются заявлением о действующем праве.\n\n'
        header+='|ID|Формула|Единицы и область|Страница задания|Слайд лекции7|Класс|Тест|Артефакт|\n|---|---|---|---|---|---|---|---|\n'
        (docs/'formula_registry.md').write_text(header+'\n'.join('|'+ '|'.join(r)+'|' for r in FORMULAS),encoding='utf-8')
        trace='# Матрица требований\n\n|Требование / формула|PDF|Лекция7|Ответственность|Проверка|Результат|\n|---|---|---|---|---|---|\n'
        trace+='\n'.join('|'+ '|'.join((r[0],r[3],r[4],r[5],r[6],r[7]))+'|' for r in FORMULAS)
        trace+='\n|PDF→CSV→DTO|2–15|—|PdfExtractionService,DataRepository|test_bad_csv,test_invalid_pdf|data/*.csv, source_manifest.json|\n|Независимый Excel|13–14|—|ExcelGroundTruthWriter,ComparisonService|test_empty_cache_never_matches|Ground_Truth.xlsx,reconciliation.csv|\n|Сценарии и стрессы|14–15|—|ScenarioService|test_scenarios|scenario_metrics.csv,stress_deltas.csv|\n|Графики и Word|15|—|ChartValidationService,WordReportWriter|test_chart_axis_validation,test_report_embeds_sections_in_order|DOCX,visual_review.json|\n|Единый pipeline, аудит и ZIP|14–15|—|PipelineController,ArtifactService|test_output_cannot_escape_app, аудит ZIP|run_manifest.json,HARNESS_LOG.xlsx,ZIP|\n'
        (docs/'requirements_traceability.md').write_text(trace,encoding='utf-8')
        (docs/'SOURCE_ISSUES.md').write_text('# Проблемы источника\n\n'+'\n\n'.join(f"## {i['id']} — PDF {i['page']}\n\n{i['issue']}\n\nРешение: {i['decision']}\n\nПроверка: {i['test']}." for i in SOURCE_ISSUES),encoding='utf-8')
        (docs/'assumptions_and_decisions.md').write_text('''# Допущения и решения

- Используются только учебные входы PDF; актуальное законодательство и реальные рыночные ставки не подмешиваются.
- Payout=100% положительного операционного денежного потока после CIT. Нет данных о юридически распределяемой прибыли, резервах или долговых ковенантах. Parent CF — модель доступных перечислений, не гарантия дивидендов.
- Cash tax неотрицателен; нет придуманного refund или переноса убытков. R&D credit начисляется пропорционально времени работы; DEU работает полные годы.
- Ожидаемая субсидия сразу уменьшает CF0 и базу амортизации по заданию. Не моделируется ее второе поступление.
- NWC фиксирован, не зависит от lead time. Возврат по окончании эксплуатации, полностью и без WHT.
- PI использует все положительные и отрицательные дисконтированные потоки, включая NWC. DPP интерполируется линейно внутри календарного года. IRR решается как полином в дисконт-факторе; все положительные вещественные корни проверяются по невязке.
- TV=0, остаточная стоимость, инфляция операционных цен, валюты и заемное финансирование не заданы.
- Excel: cashflows сравниваются построчно; atol=0.01 USD и rtol=1e−10, ставки/PI/DPP atol=1e−8. Дисперсия USD² проверяется относительным допуском.
- Три вероятностных сценария не являются Monte Carlo; σ учитывает только заданный дискретный набор, а не весь риск проекта.
- Сравнение NPV допустимо для взаимоисключающих локаций заданного объема, но не заменяет проверку финансирования, ликвидности, технической выполнимости и изменяемых реальных правил.
- Непересчитанный Excel и непросмотренные изображения никогда не получают PASS. Визуальный аудит привязан к SHA256.
''',encoding='utf-8')
        write_json(docs/'source_issues.json',SOURCE_ISSUES)
