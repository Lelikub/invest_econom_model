# Реестр формул

GRP из задания обозначается CRP. Учебные фискальные условия не являются заявлением о действующем праве.

|ID|Формула|Единицы и область|Страница задания|Слайд лекции7|Класс|Тест|Артефакт|
|---|---|---|---|---|---|---|---|
|RISK_CRP|spread × volatility|Доли ставки; volatility безразмерна|12|3|CountryRiskCalculator|test_pdf_controls|risk_rates.csv|
|RISK_GPR|base + gamma × max(0,(IGPR−mean)/sigma)|gamma из п.п./σ переводится в долю/σ|12|7|GeopoliticalRiskCalculator|test_monotonic_risk|risk_rates.csv|
|RISK_RATE|WACC + CRP + GPR|Годовая ставка, r>−1|12|4|GeopoliticalRiskCalculator|test_identities|risk_rates.csv|
|CAPEX_GROSS|CAPEX_base(1+inflation)(1+equip_duty(1−duty_free))|USD t0|12|22,24|CAPEXAndSubsidyCalculator|test_capex_exemption_and_advance|capex.csv|
|SUBSIDY_PV|gross × alpha × Papproval × (1−Pclawback)/(1+rgov)^tsub|Ожидаемая PV, USD, не гарантированный грант|12|21,22,24|CAPEXAndSubsidyCalculator|test_no_subsidy_boundary|capex.csv|
|CAPEX_NET|gross−subsidy_PV; CF0=−net|USD; субсидия второй раз не поступает|8,12|24|CAPEXAndSubsidyCalculator|test_identities|capex.csv|
|SUPPLY_PRICE|shareEU PriceEU + shareAsia PriceAsia|USD/m²|9–12|23|TariffAndLogisticsCalculator|test_pdf_controls|supply_chains.csv|
|REVENUE|Volume × [weighted(1−out)−shareEU PriceEU CBAM]|USD/year; CBAM только с контрактных отгрузок в ЕС|12|23|TariffAndLogisticsCalculator|test_cbam_and_double_count|annual_cashflows.csv|
|OPEX|Volume × raw(1+input_duty+in)+fixed × load|USD/year; пошлина и логистика аддитивны|12|23|TariffAndLogisticsCalculator|test_cbam_and_double_count|annual_cashflows.csv|
|DEPRECIATION|netCAPEX / N × load|USD/year; сумма D&A=netCAPEX|2,8|23 (D&A), база уточнена заданием|DepreciationCalculator|test_calendar|annual_cashflows.csv|
|CIT|max(0,max(EBIT min(nominal,holiday)−credit,EBIT floor))|USD/year; без cash refund. Буквальная версия без max(0,…)|5,13|17,21,23,25|FiscalTaxCalculator|test_cash_tax|taxation.csv|
|FCFF|investment + EBIT−cashTax+D&A−NWC_change|USD/calendar year; NWC положителен при вложении|8,13|23|CashFlowCalculator|test_identities|annual_cashflows.csv|
|WHT_ECONOMIC|investment+NWC_effect+operating−max(0,operating)WHT|USD; payout=100% положительного operating CF|13|25–26 (контуры WHT); приоритет заданию|WithholdingTaxCalculator|test_wht|source_sensitivity.csv|
|WHT_LITERAL|IF(FCFF≤0,FCFF−NWC_change(1−WHT),FCFF−NWC_change)|Точная запись PDF; SOURCE_CONFLICT/NON_AUTHORITATIVE|13|Не эквивалентна текстовому принципу|WithholdingTaxCalculator|test_literal_pdf_exact_typography|source_sensitivity.csv|
|NPV|Σ CFt/(1+r)^t; TV=0|USD; календарь t=0…T|13|5 (DCF пример); явная календарная сумма — определение модели|FinancialMetricsCalculator|test_metrics_roots_and_payback|base_metrics.csv|
|IRR|Все вещественные корни Σ CFt xt=0, x>0; IRR=1/x−1|Доля/год; UNIQUE/NO_ROOT/MULTIPLE_ROOTS|13 (требование метрики)|Отдельная формула IRR в лекции не найдена; численный метод документирован|FinancialMetricsCalculator|test_metrics_roots_and_payback|base_metrics.csv|
|PI|PV положительных CF / |PV отрицательных CF||Безразмерно; включает поздний NWC отток|13 (требование метрики)|Определение выбрано моделью, точный слайд не заявляется|FinancialMetricsCalculator|test_pi_includes_nwc|base_metrics.csv|
|DPP|(t−1)−CumPV(t−1)/PV(t) при первом CumPV≥0|Календарные годы; интерполяция внутри года, NOT_REACHED|13 (требование метрики)|Определение интерполяции принято моделью|FinancialMetricsCalculator|test_metrics_roots_and_payback|base_metrics.csv|
|SCENARIO|E=Σ pNPV; Var=Σp(NPV−E)²; σ=√Var|USD; USD²; USD. Дискретные сценарии, не Monte Carlo|14–15|Метод дискретного ожидания; точный слайд не заявляется|ScenarioAggregationCalculator|test_statistical_probabilities|scenario_statistics.csv|