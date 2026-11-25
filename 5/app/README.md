# Практическая работа № 5 ФИП

Модель квартального производства с технологическим браком и фиксированными пусками, а также независимый трёхлетний портфель из семи проектов. Пайплайн извлекает поля из PDF, нормализует и повторно загружает CSV, запускает расчёты, тесты, Excel Solver, анализ и упаковку.

## Запуск

Требуется Python 3.11+ и зависимости из requirements.txt. Команда установки из корня репозитория:

```powershell
python -m pip install -r 5/app/requirements.txt
python 5/app/main.py
```

Из другого рабочего каталога передайте абсолютный путь к main.py. Относительные пути проекта вычисляются по расположению main.py. В распакованном ZIP используйте `python main.py` или абсолютный путь. Приоритет источника задания — `5/task`, `5/data`, переносимая копия `data/source_assignment.pdf`. Исходный PDF в рабочей копии находится в `5/data` и совпадает с GitHub. Локальные файлы 1–4 используются как справочные материалы. Команда не требует изменений в этих каталогах.

Для нативного отчёта XLSX нужен Microsoft Excel с локальной надстройкой Solver и доступом к COM-сеансу. Word и PowerPoint используются для открытия и экспорта офисных файлов в PDF. Если COM недоступен, книга сохраняет формулы, численные сравнения SciPy/CBC и перебор остаются в CSV, а статус отражает ограничение. Флаги `--skip-excel` и `--skip-editors` подходят для ОС без Microsoft Office.

## Архитектура и проверки

- ApplicationInterface → PipelineController → DataRepository, DataValidationService и сервисы расчёта → frozen DTO. Фасад ProductionAndPortfolioOptimizer делегирует моделям производства и портфеля.
- HiGHS проверяет допустимость, верхние границы и MIPGap. PuLP/CBC независимо решает обе задачи. Переборы 8 режимов оборудования и 128 бинарных портфелей служат отдельными сертификатами.
- Solver Excel использует Simplex LP для LP и Fixed LP и линейный целочисленный режим для MILP и Knapsack. В книге сохраняются нативные отчёты устойчивости для обеих LP. Статус COM и значения после пересчёта записываются в reconciliation.csv.
- `python -m unittest discover -s tests -v` из 5/app запускает модульные, интеграционные, краевые и solver-тесты. Пайплайн запускает их автоматически.
- SHA256 источников и версии решателей в run_manifest.json. При сбое текущее состояние фиксируется в этом манифесте и logs, предыдущий завершённый output остаётся отдельным.
- Проверки PNG и офисных документов сохраняются в output. Результат ручного осмотра относится к совпавшим SHA256 PNG и подписям отрисованных страниц. Обновление данных сбрасывает несовпавшие подтверждения.
- Коды выхода 0 при завершении (в том числе с явно указанными ограничениями), 1 при сбое.

## Результаты

Ground_Truth.xlsx, reconciliation.csv, HARNESS_LOG.xlsx и HARNESS_LOG.csv содержат формулы, данные сверки и журнал. Таблицы и изображения находятся в output/tables и output/charts. Два отчёта DOCX, пятислайдовая презентация и текст защиты находятся в output. Переносимый ZIP содержит исходники, входы, отчёты и проверки. package_manifest.json хранит CRC-проверяемый список файлов с SHA256.

Методические источники перечислены в docs/requirements_traceability.md, docs/formula_registry.md и docs/SOURCE_ISSUES.md. Интерфейс автоматизации Excel Solver использует документированные функции Microsoft. [SolverOk](https://learn.microsoft.com/en-us/office/vba/excel/concepts/functions/solverok-function) · [SolverFinish](https://learn.microsoft.com/en-us/office/vba/excel/concepts/functions/solverfinish-function)
