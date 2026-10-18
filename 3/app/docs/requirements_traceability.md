# Трассируемость требований

Детальные вычисления, единицы, входы, классы и независимые проверки перечислены в [formula_registry.md](formula_registry.md).

| Требование | Источник | Реализация | Проверка | Артефакт / отчёт |
|---|---|---|---|---|
| Инвентаризация, SHA256, версии, коммит | Промт §1–2 | PipelineController | Файлы реально существуют | run_manifest.json / §3 |
| Все таблицы PDF + происхождение | PDF 2–5, промт §3 | PdfExtractionService,DataRepository | Полнота, единицы, контрольные входы, неизменность котировок | data/*.csv, source_manifest.json / §4 |
| Interface→Controller→Service→Model; отдельные калькуляторы | Промт §4 | src/interface.py,controller.py,models.py,services/,calculators/ | unit + review | исходный код / §5 |
| Этап 1: 8 базовых результатов | PDF 5–6 | MetricService | Excel формулы и кэш, инварианты | Ground_Truth.xlsx,base_metrics.csv / §6 |
| Этап 2: CSV→месяцы→OLS→сравнение beta | PDF 6–7 | MarketDataService | Даты, цены, выборка, синтетическая прямая | monthly_*.csv,ols_summary.csv,beta_comparison.csv / §7 |
| Этап 3: beta=0,D/E=0,t=0 | PDF 7–8 | TestService,pytest | Фактический запуск | test_results.csv,tests.log / §8 |
| Этап 4: все 6 шоков и 15 выходов | PDF 8–10 | ScenarioService,StressShocksCalculator | Excel + нулевой/общий/6 изолированных сценариев | stress_metrics.csv,shock_diagnostics.csv,comparison.csv / §9 |
| Этап 5: lockup, каскад и конфликт DebtService | PDF 10–11 | CashWaterfallCalculator,CovenantService | Баланс, границы 1/1.3, отдельные интерпретации | waterfall*.csv / §10 |
| Независимая сверка | Промт §6 | ExcelService,ComparisonService | Реальный COM-процесс, таймаут, кэш | reconciliation.csv / §12 |
| Фактические ошибки и сомнения, история | PDF 11, промт §7 | LoggingService,HarnessLogWriter | Только наблюдаемые события | HARNESS_LOG.xlsx,logs/*.log,events.jsonl / §13 |
| 8 обязательных + чувствительность графиков | Промт §8 | ChartWriter,ChartValidationService | Таблицы, конечность, bounding boxes, PNG + просмотр человеком/агентом отдельно | charts/*.png,chart_catalog.csv / §11 |
| Академический русский DOCX, Excel, ZIP | PDF 11–12, промт §9 | ReportingService | DOCX таблицы/рисунки, Excel, ZIP CRC | Итоговый_отчет_ФИП_Практическая_3.docx / все разделы |
| Инженерное резюме, 10 лет, поддержка | PDF 12 | DiscountEffectCalculator,ReportingService | Единичный поток, без выдуманной IRR | discount_factors.csv / §14 |
| Неоднозначности и недостающие входы | Промт §10 | SOURCE_ISSUES.md,HarnessLogWriter | Фактическое содержимое источников | docs/SOURCE_ISSUES.md / §15 |
| Одна команда + автоматические тесты + статусы | Промт §11–12 | ApplicationInterface,PipelineController | Полный запуск; FAILED при критических ошибках | README.md,run_manifest.json |
