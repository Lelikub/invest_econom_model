# Матрица требований

|Требование / формула|PDF|Лекция7|Ответственность|Проверка|Результат|
|---|---|---|---|---|---|
|RISK_CRP|12|3|CountryRiskCalculator|test_pdf_controls|risk_rates.csv|
|RISK_GPR|12|7|GeopoliticalRiskCalculator|test_monotonic_risk|risk_rates.csv|
|RISK_RATE|12|4|GeopoliticalRiskCalculator|test_identities|risk_rates.csv|
|CAPEX_GROSS|12|22,24|CAPEXAndSubsidyCalculator|test_capex_exemption_and_advance|capex.csv|
|SUBSIDY_PV|12|21,22,24|CAPEXAndSubsidyCalculator|test_no_subsidy_boundary|capex.csv|
|CAPEX_NET|8,12|24|CAPEXAndSubsidyCalculator|test_identities|capex.csv|
|SUPPLY_PRICE|9–12|23|TariffAndLogisticsCalculator|test_pdf_controls|supply_chains.csv|
|REVENUE|12|23|TariffAndLogisticsCalculator|test_cbam_and_double_count|annual_cashflows.csv|
|OPEX|12|23|TariffAndLogisticsCalculator|test_cbam_and_double_count|annual_cashflows.csv|
|DEPRECIATION|2,8|23 (D&A), база уточнена заданием|DepreciationCalculator|test_calendar|annual_cashflows.csv|
|CIT|5,13|17,21,23,25|FiscalTaxCalculator|test_cash_tax|taxation.csv|
|FCFF|8,13|23|CashFlowCalculator|test_identities|annual_cashflows.csv|
|WHT_ECONOMIC|13|25–26 (контуры WHT); приоритет заданию|WithholdingTaxCalculator|test_wht|source_sensitivity.csv|
|WHT_LITERAL|13|Не эквивалентна текстовому принципу|WithholdingTaxCalculator|test_literal_pdf_exact_typography|source_sensitivity.csv|
|NPV|13|5 (DCF пример); явная календарная сумма — определение модели|FinancialMetricsCalculator|test_metrics_roots_and_payback|base_metrics.csv|
|IRR|13 (требование метрики)|Отдельная формула IRR в лекции не найдена; численный метод документирован|FinancialMetricsCalculator|test_metrics_roots_and_payback|base_metrics.csv|
|PI|13 (требование метрики)|Определение выбрано моделью, точный слайд не заявляется|FinancialMetricsCalculator|test_pi_includes_nwc|base_metrics.csv|
|DPP|13 (требование метрики)|Определение интерполяции принято моделью|FinancialMetricsCalculator|test_metrics_roots_and_payback|base_metrics.csv|
|SCENARIO|14–15|Метод дискретного ожидания; точный слайд не заявляется|ScenarioAggregationCalculator|test_statistical_probabilities|scenario_statistics.csv|
|PDF→CSV→DTO|2–15|—|PdfExtractionService,DataRepository|test_bad_csv,test_invalid_pdf|data/*.csv, source_manifest.json|
|Независимый Excel|13–14|—|ExcelGroundTruthWriter,ComparisonService|test_empty_cache_never_matches|Ground_Truth.xlsx,reconciliation.csv|
|Сценарии и стрессы|14–15|—|ScenarioService|test_scenarios|scenario_metrics.csv,stress_deltas.csv|
|Графики и Word|15|—|ChartValidationService,WordReportWriter|test_chart_axis_validation,test_report_embeds_sections_in_order|DOCX,visual_review.json|
|Единый pipeline, аудит и ZIP|14–15|—|PipelineController,ArtifactService|test_output_cannot_escape_app, аудит ZIP|run_manifest.json,HARNESS_LOG.xlsx,ZIP|
