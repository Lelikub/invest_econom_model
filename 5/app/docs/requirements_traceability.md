# Практическая работа № 5. Реестр требований и план реализации

Источник: девятистраничное «Задание 5», Потапов Г. Г. Методический источник: «Лекция 9 ФИП слайды», 35 слайдов. Номера ниже соответствуют печатной нумерации и страницам PDF.

| Этап и блок | PDF / лекция 9 | Класс или модуль | Проверка | Артефакт |
|---|---|---|---|---|
| Извлечение и контроль, 0–2 | 2–5, 7–8 / 5–10, 25–27 | PdfExtractor, DataRepository, DataValidationService | test_source, test_invalid, test_currency | data/inputs.csv, run_manifest.json |
| 1. Эффективные нормы, LP и MILP, 3 | 2–3, 5–6 / 5–10 | OperationsOptimizer, OperatingModel | test_operations, test_yield_and_zero, test_independent_certificate | operations.csv, resources.csv, effective.csv |
| 1–2. Fixed LP, двойственность, 3 | 5–6 / 12–24 | OperationsOptimizer | test_duality, test_negative | resources.csv, reduced_costs.csv |
| 1–2. PI, связи, оптимальность, 4 | 3–6 / 25–27 | PortfolioOptimizer | test_portfolio, test_certificate | portfolio_comparison.csv, portfolio_pi.csv, Ground_Truth.xlsx |
| 3. Четыре краевых случая, 5 | 7 / 9–10, 24, 27 | ScenarioAnalysis, Harness | test_zero_nmp, test_negative, test_extruder, test_exclusion | edge_cases.csv, HARNESS_LOG.xlsx, logs/tests.log |
| 4. ε, перебор, нормированная свёртка, 6 | 7 / 28–32 | ParetoAnalysis | test_pareto | pareto_all_feasible.csv, pareto_nondominated.csv, epsilon_solutions.csv, weighted_solutions.csv |
| 5. Финансовый и экологический стресс, 7 | 8 / дополнение к 9, 27, 32 | ScenarioAnalysis | test_stresses | stress_portfolio.csv, stress_operations.csv |
| 6. MRT, зоны, дискретное колено, 7 | 8–9 / 34–35 для интерпретации | ParetoAnalysis | test_pareto | mrt.csv, knee.csv |
| 7. Пять слайдов и ролевая защита, 8–10 | 9 / 34–35 | ReportService, presentation, audit | OOXML, контроль таблиц и графиков, CRC и SHA256 | два отчёта DOCX, сценарий DOCX, PPTX, ZIP |

Порядок работ: извлечение и приёмочные тесты → вычислительная модель и независимые сертификаты → Excel, сверка и запуск тестов → Парето и стрессы → выгрузка и аудит → документы → упаковка. Путь исходников вычисляется от main.py. Все записи ограничены 5/app. Перед финальным запуском выполняется проверка просмотренных SHA256 графиков.
