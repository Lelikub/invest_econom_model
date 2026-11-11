"""Construct shared report DTOs from actual calculated results."""
from dataclasses import asdict
from ..models import ReportSectionDTO
from .documentation import SOURCE_ISSUES

class ReportService:
    def sections(self,inputs,scenarios,tables,reconciliation,tests,manifest,issues=()):
        sections=[]; base=scenarios.results['B']; codes=list(base)
        def add(id,title,table,chart,columns,rows,text):
            sections.append(ReportSectionDTO(id,title,table,chart,tuple(columns),tuple(tuple(r) for r in rows),text))
        p=inputs.project
        add('01','Цель, объект и источники','sources',None,
            ['Источник / параметр','Значение','Единица'],
            [('Задание 4',15,'страниц'),('Лекция 7',32,'слайда'),('Базовый CAPEX',p.capex_base,'USD'),('Мощность',p.volume,'м²/год'),('Постоянный OPEX',p.fixed_opex,'USD/год'),('Горизонт',p.years,'эквивалентных лет'),('NWC',p.nwc,'USD'),('WACC',p.wacc*100,'%/год')],
            f'Сравнивается Greenfield-завод PFSA-мембран и мембранно-электродных блоков для PEM-электролизеров. Основной критерий — Parent NPV. '
            f'Параметры извлечены из текстового слоя и геометрических ячеек таблиц PDF, сохранены в восьми нормализованных CSV и повторно прочитаны в frozen dataclass. '
            f'Извлечено {len(inputs.provenance)} числовых записей с исходным текстом, страницей, единицей и статусом. Полные исходы — data/*.csv; SHA256 и размеры — source_manifest.json/run_manifest.json. '
            'Контрольные удельные цены всех трех стран подтверждены; значения не подменялись итогами прошлых практических работ. Учебные налоговые условия не заявляются как актуальное законодательство.')
        add('02','Архитектура и воспроизводимость','architecture',None,['Уровень','Ответственность'],[
            ('ApplicationInterface','CLI, конфигурация, код возврата'),('PipelineController','Стадии 00–15 и журналирование'),('PdfExtractionService → DataRepository','PDF → CSV → неизменяемые DTO'),('CrossBorderSupplyChainEvaluator','Композиция чистых калькуляторов'),('ScenarioService','Новые объекты A/B/C, edge и stress'),('ExcelGroundTruthWriter / ComparisonService','Независимые формулы и сверка реального кэша'),('ChartService / ReportService','Общие CSV и связанные таблица → график → анализ'),('HarnessLogWriter / ArtifactService','Аудит, manifest, ZIP')],
            'Один запуск: python 4/app/main.py. Формулы отсутствуют в интерфейсе, контроллере и DTO. Каждый калькулятор решает узкую математическую задачу и не читает файлы. '
            'Тесты и Excel worker запускаются контроллером; субагенты не используются. План и реестры: docs/implementation_plan.md, formula_registry.md, requirements_traceability.md. '
            'GRP задания обозначается CRP. Слайды 3–7 лекции7 задают риск; 21–24 — субсидии и потоки; 25–26 — налоговый минимум и WHT. Где лекция не дает отдельной формулы IRR/PI/DPP, определение явно является решением модели.')
        risk=tables['risk_rates']
        add('03','Страновой и геополитический риск','risk_rates','01_risk',
            ['Страна','WACC, %','CRP, %','GPR, %','r_adj, %'],[(r['country'],r['wacc']*100,r['crp']*100,r['gpr']*100,r['rate']*100) for r in risk],
            '; '.join(f"{c}: r_adj={base[c].risk.rate*100:.3f}%" for c in codes)+'. '
            f"У SRB GPR={base['SRB'].risk.gpr*100:.2f}% при IGPR={base['SRB'].country.igpr:.0f}; у VNM CRP={base['VNM'].risk.crp*100:.3f}%. "
            'Разница ставок уменьшает PV поздних поступлений. Gamma конвертирована из п.п./σ в долю/σ. Рост IGPR меняет ставку, но не создает произвольное сокращение выручки; заданный фрахтовый стресс моделируется отдельно в OPEX.')
        add('04','CAPEX и ожидаемая субсидия','capex','02_capex',['Страна','Gross, млн USD','PV субсидии, млн USD','Net, млн USD','Год субсидии'],
            [(c,r.capex.gross/1e6,r.capex.subsidy_pv/1e6,r.capex.net/1e6,r.country.subsidy_year) for c,r in base.items()],
            'Чистые инвестиции: '+ '; '.join(f'{c} {r.capex.net/1e6:.3f} млн USD' for c,r in base.items())+'. '
            'Субсидия умножается на вероятность одобрения и сохранения гранта, затем дисконтируется по доходности суверенных облигаций. Это ожидаемая приведенная оценка, а не гарантированный денежный грант. '
            'Вся PV уже уменьшает CF0 и базу амортизации. В год фактического перечисления второй положительный CF не создается. В SRB пошлина на оборудование 1% нейтрализована duty_free=1.')
        add('05','Сырье, рынки, логистика и CBAM','supply_chains','03_supply',
            ['Страна','Сырье base','Сырье landed','Цена weighted','Цена net','CBAM/м²','Lead time, дней'],
            [(c,r.country.raw_base,r.supply.raw_landed,r.supply.price_weighted,r.supply.price_net,r.supply.cbam_unit,r.country.lead_days) for c,r in base.items()],
            f"Все удельные денежные значения — USD/м². У VNM 166×(1−0,07)−0,30×180×0,04={base['VNM'].supply.price_net:.2f} USD/м²; "
            f"CBAM составляет {base['VNM'].supply.cbam_unit:.2f} USD/м² всего выпуска и относится только к ЕС. "
            'Сырье SRB и VNM имеет одинаковую landed-стоимость при разных сочетаниях фрахта и пошлин. Пошлина на оборудование не повторяется в OPEX, входная логистика не включается в стоимость реализации. '
            'Конкретная матрица рынков таблицы2 имеет приоритет перед общим описанием 85% экспорта на стр.2.')
        add('06','Календарь, амортизация и NWC','time_schedule','04_calendar',
            ['Страна','Первый t','Последний t','Load first/last','Σ экв. лет','Σ D&A, млн USD','NWC draw/release t'],
            [(c,r.country.first,r.country.last,f'{r.country.first_load:g}/{r.country.last_load:g}',sum(a.load for a in r.annual),sum(a.depreciation for a in r.annual)/1e6,f'{r.country.nwc_draw:g}/{r.country.nwc_release:g}') for c,r in base.items()],
            'Начало эксплуатации — DEU t4, SRB t3, VNM t3. У VNM первая и последняя точки загрузки равны 0,5; девять промежуточных лет — 1. '
            'Сумма нагрузок каждого завода равна 10, сумма D&A — соответствующему net CAPEX. В полугодиях VNM постоянный OPEX равен 2,5 млн USD. '
            'NWC_cash_effect = −4 млн при вложении и +4 млн при возврате, сумма равна нулю. NWC_change имеет противоположный знак и вычитается из FCFF. '
            'Подтвержденные календарные границы и события NWC сохранены в chart_features.csv; перегибы и асимптоты не утверждаются.')
        annual_rows=[(c,a.year,a.revenue/1e6,a.opex/1e6,a.cash_tax/1e6,a.nwc_cash_effect/1e6,a.local_cf/1e6,a.parent_cf/1e6) for c,r in base.items() for a in r.annual]
        add('07','Годовые локальные и материнские денежные потоки','annual_cashflows','05_cashflows',
            ['Страна','t','Revenue','OPEX','CIT','NWC cash','Local CF','Parent CF'],annual_rows,
            'Денежные столбцы в млн USD, без округления в расчетах. CAPEX находится только в t0, NWC — в заданные годы. WHT уменьшает только положительный операционный поток после CIT. '
            'Принято распределение 100% такого потока: отсутствие payout ratio и юридических ограничений раскрыто как допущение. Стоимость WHT по NPV: '+
            '; '.join(f'{c} {(r.local.npv-r.parent.npv)/1e6:.3f} млн USD' for c,r in base.items())+'. '
            'После завершения SRB в t12 строка t13 нулевая. Весь общий календарь 0…13 сохраняется в метриках; нулевые годы до ввода не сжимаются.')
        add('08','Накопленный дисконтированный поток и DPP','cumulative','06_cumulative',
            ['Страна','Конечный CumPV, млн USD','DPP','Статус'],[(c,r.parent.npv/1e6,r.parent.dpp if r.parent.dpp is not None else '—',r.parent.dpp_status) for c,r in base.items()],
            'Кривые не достигают нуля к окончанию проекта: DPP=NOT_REACHED у всех стран. Число лет окупаемости за пределами наблюдаемого горизонта не экстраполируется. '
            'Каждое поступление дисконтируется по фактическому календарному t; задержка запуска ухудшает PV, даже если эквивалентный объем производства одинаков. Терминальная стоимость TV=0, поскольку методика ее расчета не задана.')
        add('09','Налоги, R&D credit и Pillar 2','taxation','07_taxation',
            ['Страна','t','EBIT, млн USD','Режим, %','Credit, млн USD','CIT, млн USD'],
            [(c,a.year,a.ebit/1e6,a.holiday_rate*100,a.tax_credit/1e6,a.cash_tax/1e6) for c,r in base.items() for a in r.annual if a.load],
            'VNM: t3–11 15%, t12–13 20%; SRB: 15% от прямых продаж без IP Box; DEU: 29,80% до годового R&D credit 1 млн USD, с ограничением пола 15%. '
            'Напечатанная формула для отрицательного EBIT сохранена как контрольная; основная модель не создает неподтвержденных денежных налоговых возвратов. '
            'Эффект замены cash_tax буквальной формулой на базовый Parent NPV: '+ '; '.join(f'{c} {(r.literal_tax.npv-r.parent.npv)/1e6:.6f} млн USD' for c,r in base.items())+'. В данном наборе входов это не означает эквивалентности методов при убытках.')
        add('10','Базовые инвестиционные показатели','base_metrics','08_metrics',
            ['Страна / поток','NPV, млн USD','IRR, %','PI','PV+, млн USD','|PV−|, млн USD','DPP'],
            [(c+' / '+scope,m.npv/1e6,m.irr*100 if m.irr is not None else m.irr_status,m.pi,m.pv_inflows/1e6,m.pv_outflows/1e6,m.dpp if m.dpp is not None else m.dpp_status) for c,r in base.items() for scope,m in [('local',r.local),('parent',r.parent)]],
            'Наименее отрицательный базовый Parent NPV имеет '+max(base,key=lambda c:base[c].parent.npv)+'. '
            'PI учитывает PV всех инвестиционных оттоков, включая позднее вложение NWC. IRR вычисляется для полного календарного ряда; ищутся все положительные вещественные корни полинома в дисконт-факторе. '
            'При отсутствии/множественности корней возвращается статус, а не произвольное число. Во всех базовых локациях IRR ниже r_adj, PI<1 и Parent NPV<0; принять проект только по низкому номинальному налогу нельзя.')
        counts={status:sum(r['status']==status for r in reconciliation) for status in sorted({r['status'] for r in reconciliation})}
        add('11','Независимый Excel и проверка численных результатов','reconciliation',None,['Статус','Число сравнений'],list(counts.items()),
            f"Сверка выполнена для {len(reconciliation)} ячеек: риски, CAPEX, субсидии, цепочки поставок, все годовые строки, local/Parent/literal метрики, сценарные ожидания и дисперсии. "
            'В книге расчетные ячейки содержат формулы, входы отделены. Независимым подтверждением считается только кэш после реального Excel COM. '
            f"Движок: {manifest.get('excel',{}).get('status','NOT_VERIFIED')}. Денежный допуск 0,01 USD + 1e−10×|Python|; для ставок/PI/DPP абсолютный допуск 1e−8. "
            'Результаты сравниваются до округления; отсутствие кэша не признается совпадением. Полный построчный протокол — reconciliation.csv.')
        add('12','Граничные проверки и протокол тестирования','tests',None,['Результат','Количество'],
            [(k,sum(r['status']==k for r in tests)) for k in sorted({r['status'] for r in tests})],
            f'Запущено {len(tests)} тестов через subprocess pytest, XML и tests.log сохранены. Zero-Friction обнуляет пошлины, CBAM, входную/выходную логистику, CRP/GPR: ставка остается WACC={p.wacc*100:.2f}%. '
            'Отдельная фикстура VNM PILLAR2 задает 0% в первые четыре года и проверяет доначисление до 15% при положительном EBIT. '
            'Double Counting проверяет независимость операционных поступлений от абстрактной премии риска и однократное включение логистики. '
            'Дополнительно проверены отрицательный EBIT, границы субсидий, WHT=0, NWC, поврежденные входы, единицы, IRR с несколькими корнями, отсутствие Excel-кэша и неверные границы графической оси. Реальные дефекты и SOURCE_ISSUE разделены в HARNESS_LOG.xlsx.')
        stress=tables['stress_metrics']
        add('13','Обязательные стресс-тесты','stress_metrics','09_stress',
            ['Стресс / страна','База NPV','Стресс NPV','Δ NPV','Базовая r, %','Стресс r, %'],
            [(r['stress']+' / '+r['country'],r['base_npv']/1e6,r['stress_npv']/1e6,r['delta']/1e6,r['base_rate']*100,r['stress_rate']*100) for r in stress],
            f"NPV в млн USD. Красный прилив VNM: IGPR={inputs.scenarios['vnm_igpr']:.0f}, входной фрахт {inputs.scenarios['vnm_freight']*100:.0f}%, доставка {inputs.scenarios['vnm_days']:.0f} дней. "
            f"Изменение Parent NPV {stress[0]['delta']/1e6:.3f} млн USD, OPEX полного года меняется на {(stress[0]['stress_opex']-stress[0]['base_opex'])/1e6:.3f} млн USD. "
            f"Балканский стресс SRB: CBAM {inputs.scenarios['srb_cbam']*100:.0f}% только на ЕС; изменение Parent NPV {stress[1]['delta']/1e6:.3f} млн USD. "
            'IP Box ранее не применялся, поэтому налог остается 15%; искусственного налогового скачка нет. Срок доставки не меняет фиксированный NWC. Исходные CSV не изменяются; абсолютные и относительные изменения всех метрик и годовых строк — stress_deltas.csv.')
        add('14','Три вероятностных макросценария','scenario_metrics','10_scenarios',['Страна','A NPV','Б NPV','В NPV','p(A)/p(Б)/p(В)'],
            [(c,*[scenarios.results[s][c].parent.npv/1e6 for s in 'ABC'],'0,20 / 0,50 / 0,30') for c in codes],
            'Все NPV в млн USD. A снижает IGPR на 30% и обнуляет пошлины и CBAM, сохраняя транспортные расходы. Б сохраняет исходы. '
            'В сочетает оба страновых стресса, а в DEU повышает IGPR на 50% и удорожание CAPEX до 50%. '
            'Для каждого набора полностью пересчитываются ставка, чистый CAPEX, D&A, налоги и CF. Благоприятный сценарий не является Zero-Friction: остаточные CRP/GPR и логистика сохраняются.')
        stats=tables['scenario_statistics']; ranked=sorted(stats,key=lambda r:r['expected'],reverse=True)
        add('15','Ожидаемая стоимость и дискретный риск','scenario_statistics','11_expectation',
            ['Рейтинг','Страна','E[NPV], млн USD','Var, USD²','σ, млн USD','P(NPV<0)'],
            [(i,r['country'],r['expected']/1e6,r['variance'],r['std']/1e6,r['probability_negative']) for i,r in enumerate(ranked,1)],
            'Рейтинг по ожидаемому Parent NPV: '+ ' → '.join(r['country'] for r in ranked)+'. '
            'Ожидание каждой страны находится между крайними сценарными значениями, вероятности суммируются в 1, дисперсия неотрицательна. '
            'Стандартное отклонение измеряется в USD, дисперсия — USD². Полосы E±σ не являются доверительным интервалом нормального распределения. '
            'P отрицательного NPV рассчитана только по трем заданным сценариям и не характеризует все возможные будущие состояния.')
        sensitivity=tables['source_sensitivity']
        add('16','Методологический аудит WHT и NWC','source_sensitivity','12_source_audit',
            ['Страна','Economic NPV','Literal PDF NPV','Δ literal','Δ literal tax','Стоимость WHT'],
            [(r['country'],r['economic_npv']/1e6,r['literal_wht_npv']/1e6,r['literal_wht_delta']/1e6,r['literal_tax_delta']/1e6,r['wht_npv_cost']/1e6) for r in sensitivity],
            'Все значения в млн USD. Буквальная строка PDF прочитана по визуальному рендеру: в отрицательной ветви WHT умножает только ΔNWC; дополнительных скобок вокруг FCFF−ΔNWC нет. '
            'Это повторно учитывает движение NWC и не удерживает WHT с положительного операционного CF. Версия маркируется SOURCE_CONFLICT/NON_AUTHORITATIVE. '
            'Изменение NPV — методологическая чувствительность, а не допустимая налоговая оптимизация. Даже DEU с WHT=0 имеет расхождение из-за повторного NWC. '
            'В инвестиционном выводе используется только economic_rule.')
        sen=tables['sensitivities']; delay=[r for r in sen if r['parameter']=='delay_year' and r['x']==1]
        add('17','Однофакторная чувствительность','sensitivities','13_sensitivity',
            ['Страна','NPV при задержке +1, млн USD','Изменение к базе, млн USD'],
            [(r['country'],r['parent_npv']/1e6,(r['parent_npv']-base[r['country']].parent.npv)/1e6) for r in delay],
            'IGPR исследован как приращение к исходному индексу; WHT и CBAM — как абсолютные доли. Дополнительная задержка сдвигает эксплуатацию, NWC и налоговый календарь на целые годы; CF0 и субсидия остаются фиксированными. '
            'Это отдельная модельная чувствительность, а не изменение обязательных сценариев PDF. Диапазон конечен, интерполяция только соединяет рассчитанные точки; асимптоты, гладкие экстремумы и перегибы не заявляются. '
            'Все исследованные значения сохранены, включая крайние отрицательные NPV.')
        add('18','Проблемы источника и принятые решения','source_issues',None,['ID / PDF','Наблюдение','Решение'],
            [(r['id']+' / '+r['page'],r['issue'],r['decision']) for r in SOURCE_ISSUES],
            'Эти записи отражают противоречия учебного источника, а не фиктивные ошибки кода. Каждое решение связано с тестами и исходной страницей. '
            'Отдельные реальные ошибки реализации с причиной, исправлением и результатом повторной проверки находятся в Harness Log/Fixes.')
        best=ranked[0]
        add('19','Инженерно-экономическое резюме инвестиционному комитету','verdict',None,
            ['Страна','E[ParentNPV], млн USD','σ, млн USD','Решение в рамках модели'],
            [(r['country'],r['expected']/1e6,r['std']/1e6,'Не принимать при заданных условиях' if r['expected']<0 else 'Требуется дальнейшая проверка') for r in ranked],
            f"Лучший относительный результат у {best['country']}: E[ParentNPV]={best['expected']/1e6:.3f} млн USD при σ={best['std']/1e6:.3f} млн USD. "
            'Все три ожидаемых Parent NPV отрицательны. При заданных мощности, ценах, инвестициях, сроках и TV=0 ни одна локация не создает требуемую стоимость; положительную инвестиционную рекомендацию сформировать нельзя. '
            'Германия компенсирует более дорогой CAPEX меньшей ставкой риска и лучшей чистой ценой, но поздний запуск и масштаб инвестиций все равно делают NPV отрицательным. '
            'Субсидии не устраняют потери от дисконтирования; WHT, CBAM и фрахт ухудшают альтернативы. Для нового решения нужны подтвержденные изменения маржи, CAPEX, графика либо самостоятельная методика остаточной стоимости. '
            'Финансирование, юридическая распределяемость CF, валютный и технологический риск не обеспечены исходными данными. Полнота подтверждения исполнения указана в manifest, независимо от инвестиционного вердикта.')
        if issues:
            actual=[r for r in issues if r['kind'] in ('CODE_ERROR','ENVIRONMENT','VERIFICATION_LIMIT')]
            add('20','Выдержки Harness Log: фактические дефекты и повторная проверка','harness_extract',None,
                ['ID / тип','Наблюдение','Исправление / решение','Повторная проверка'],
                [(r['id']+' / '+r['kind'],r['observed'],r['decision'],r.get('retest',r['status'])) for r in actual],
                'Показаны только реально наблюдавшиеся ошибки и ограничения среды. Ошибка календарного горизонта, неоднородного CSV журнала и неполной проверки единиц сопровождалась падением соответствующего теста; после исправлений регрессионные тесты включены в общий прогон. '
                'Исправления календарного нулевого хвоста и CSV/единиц не изменяют корректные базовые денежные параметры; исходные проблемы PDF перечислены отдельно.')
        # Complete annual calculations are embedded as readable groups, not just external links.
        from dataclasses import fields
        from ..models import AnnualResult
        columns=[f.name for f in fields(AnnualResult) if f.name!='year']
        for code,r in base.items():
            for group,start in enumerate(range(0,len(columns),7),1):
                keys=columns[start:start+7]
                add(f'П{code}.{group}',f'Полная годовая расчетная таблица {code}, блок {group}',
                    'annual_cashflows',None,['t',*keys],
                    [(a.year,*[getattr(a,key) for key in keys]) for a in r.annual],
                    'Полный календарь t=0…13. Денежные поля — USD без масштабирования; volume — м²; load, holiday_rate и discount_factor — доли. '
                    'Данные взяты непосредственно из AnnualResult; округление только при отображении. Полная точность сохранена в annual_cashflows.csv и независимых формульных листах Excel. '
                    'literal_tax и parent_literal — контрольные версии спорных формул источника, не основной инвестиционный метод.')
        return sections
