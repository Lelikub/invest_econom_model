# DCF/CAPEX pipeline

Приложение выполняет всю практическую работу одной командой: читает исходный CSV, валидирует данные, рассчитывает CAPEX методом Ленга и DCF, создает формульную Excel Ground Truth, фактически пересчитывает ее Microsoft Excel, сверяет Python и Excel, запускает граничные тесты, Монте-Карло и стресс-тест, строит графики и формирует Harness Log и Word-отчет.

## Требования

- Python 3.10 или новее;
- Microsoft Excel для обязательного COM-пересчета формул;
- зависимости из `app/requirements.txt`.

Обычная установка в виртуальное окружение:

```powershell
python -m venv app/.venv
app/.venv/Scripts/python.exe -m pip install -r app/requirements.txt
app/.venv/Scripts/python.exe app/main.py
```

В текущей среде доступен изолированный Python из pgAdmin без модуля `venv`. Для него зависимости установлены локально в `app/.python-packages`, а запуск выполняется так:

```powershell
& 'C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe' app/main.py
```

Тесты:

```powershell
& 'C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe' app/run_tests.py
```

## Входы и допущения

- Исходный файл: `1/data/data.csv`; он не изменяется.
- PDF задания содержит WACC 10% и долю оборотного капитала 12%, CSV — 12% и 15%. Для обоих расчетных движков используются значения CSV; конфликт раскрывается во всех журналах и отчете.
- `I0 = TCI`, амортизируется FCI, оборотный капитал не амортизируется.
- Дополнительный CAPEX и ежегодный `ΔNWC` не заданы, поэтому в годах 1–N равны нулю.
- Терминальная стоимость не добавляется.
- PI — стандартное определение `PV будущих FCF / I0`, поскольку отдельная формула отсутствует в лекции.
- Монте-Карло: 1000 итераций, seed `20260916`, независимые логнормальные множители CAPEX (CV 30%) и Revenue (CV 20%).

## Результаты

По умолчанию создаются:

- `app/output/DCF_Ground_Truth.xlsx`;
- `app/output/Harness_Log.xlsx`;
- `app/output/Сравнение_результатов.xlsx`;
- `app/output/histogram_npv.png`;
- `app/output/s_curve_npv.png`;
- `app/output/Итоговый_отчет_ФИП.docx`;
- `app/logs/execution.log`.

Word-отчет создается только после успешных граничных тестов и сверки Python/Excel с относительным отклонением строго меньше `0,01%`.

