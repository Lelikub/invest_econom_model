"""Map existing calculated DTOs onto the user's twelve-chapter report schema."""
from dataclasses import asdict
from ..models import (ReportChapterDTO,ReportSectionDTO,ReportTextDTO,ReportHeadingDTO,ReportFormulaDTO)
from .documentation import FORMULAS,SOURCE_ISSUES

VARIABLES={
 'RISK_CRP':'spread — спред суверенного дефолта; volatility — отношение волатильностей акций и гособлигаций; CRP — страновая премия.',
 'RISK_GPR':'base — базовая премия GPR; gamma — доля ставки на одно σ; IGPR — индекс риска; mean=100 и sigma=50 — параметры нормирования из PDF.',
 'RISK_RATE':'WACC — базовая стоимость капитала; CRP — страновая премия; GPR — геополитическая премия; r — итоговая годовая ставка.',
 'CAPEX_GROSS':'CAPEX_base — базовые инвестиции; inflation — структурное удорожание; equip_duty — пошлина на оборудование; duty_free∈{0,1} — освобождение.',
 'SUBSIDY_PV':'gross — CAPEX до субсидии; alpha — доля гранта; Papproval/Pclawback — вероятности одобрения/отзыва; rgov — ставка гособлигаций; tsub — календарный год поступления.',
 'CAPEX_NET':'gross — инвестиции до гранта; subsidy_PV — ожидаемая приведенная субсидия; net — чистые инвестиции; CF0 — начальный денежный поток.',
 'SUPPLY_PRICE':'shareEU/shareAsia — доли рынков; PriceEU/PriceAsia — контрактные цены соответствующих рынков; сумма долей равна1.',
 'REVENUE':'Volume — выпуск в календарном году; weighted — взвешенная контрактная цена; out — доля выходной логистики; CBAM — ставка только на отгрузки в ЕС.',
 'OPEX':'raw — базовая удельная цена сырья; input_duty/in — пошлина/входная логистика; fixed — годовые постоянные затраты; load — годовой эквивалент загрузки.',
 'DEPRECIATION':'netCAPEX — чистая амортизируемая база; N — эквивалентные годы эксплуатации; load — доля полного года; D&A — амортизация.',
 'CIT':'EBIT — прибыль до процентов и налога; nominal/holiday — номинальная/льготная ставки; credit — R&D вычет; floor — минимальная ставка15%; cash tax — неотрицательная денежная выплата.',
 'FCFF':'investment — CF инвестиций, включая CF0; EBIT — операционная прибыль; cashTax — CIT; D&A — амортизация; NWC_change — увеличение вложенного оборотного капитала.',
 'WHT_ECONOMIC':'operating — EBIT−cashTax+D&A; WHT — ставка налога у источника; NWC_effect=−NWC_change; investment — инвестиционный CF. Предполагается распределение100% положительного operating.',
 'WHT_LITERAL':'FCFF — локальный денежный поток с NWC; NWC_change — изменение вложенного оборотного капитала; WHT — ставка удержания. Только контроль SOURCE_CONFLICT/NON_AUTHORITATIVE.',
 'NPV':'CFt — денежный поток на календарную дату t; r — r_adj соответствующей страны/сценария; T — последний календарный год; TV — терминальная стоимость, принята0.',
 'IRR':'x=1/(1+IRR) — дисконт-фактор; CFt — календарные потоки. Учитываются все вещественные x>0; отсутствие/множественность корней отмечаются статусом.',
 'PI':'PV — приведенная стоимость по r_adj; положительные CF — поступления; отрицательные CF — все оттоки, включая CAPEX и NWC.',
 'DPP':'CumPV(t−1) — накопленный дисконтированный поток до года восстановления; PV(t) — приведенное поступление за этот год. При отсутствии восстановления — NOT_REACHED.',
 'SCENARIO':'p — вероятность дискретного сценария; NPV — Parent NPV сценария; E — математическое ожидание; Var — дисперсия; σ — стандартное отклонение.'}

class TemplateReportService:
    def build(self,titles,sections,inputs,manifest,report_data=None):
        data=report_data or {}; chapters=[[] for _ in titles]; by_id={s.section_id:s for s in sections}; used=set()
        def text(ch,value,bullet=False): chapters[ch-1].append(ReportTextDTO(value,bullet))
        def table(ch,id,title,columns,rows,analysis):
            chapters[ch-1].append(ReportSectionDTO('template_'+id,title,id,None,tuple(columns),tuple(tuple(r) for r in rows),analysis))
        def take(ch,id):
            if id in by_id: chapters[ch-1].append(by_id[id]); used.add(id)
        text(1,'Цель работы — оценить размещение Greenfield-завода PFSA/PEM в Германии, Сербии и Вьетнаме с учетом странового и геополитического риска, фискальных условий и трансграничных цепочек поставок. Основной критерий инвестиционного решения — Parent NPV потоков, доступных материнской компании.')
        for task in ['Проверить исходные PDF и происхождение параметров, сохранить нормализованные CSV.',
            'Рассчитать риск, CAPEX, субсидии, операционные затраты, налоги и календарные денежные потоки.',
            'Независимо сверить Python с формулами и фактически пересчитанным кэшем Excel.',
            'Зафиксировать реальные дефекты и противоречия источника в Harness Log.',
            'Провести граничные проверки, два стресса и три вероятностных сценария; сформулировать инвестиционные выводы.']: text(1,task,True)
        text(2,'Объект — производство перфторсульфоновых полимерных мембран и мембранно-электродных блоков для PEM-электролизеров. Проект предусматривает высокотемпературный фторорганический синтез и формование пленок в чистых комнатах ISO4. Альтернативы: Германия (DEU), Сербия (SRB), Вьетнам (VNM).')
        if inputs:
            p=inputs.project
            table(2,'object','Масштаб проекта',('Показатель','Значение','Единица'),[
                ('Базовые инвестиции',p.capex_base,'USD'),('Номинальный выпуск',p.volume,'м²/год'),
                ('Постоянные затраты',p.fixed_opex,'USD/год'),('Эквивалентный горизонт',p.years,'лет'),
                ('Оборотный капитал',p.nwc,'USD')],'Параметры прочитаны из CSV после программного извлечения PDF. Страновые различия изменяют чистые инвестиции, сроки и денежные поступления при одинаковой номинальной мощности.')
        text(3,'Первичные источники параметров — PDF задания4 и лекция7. Шаблон DOCX задает структуру и оформление отчета. Производственные значения извлечены в CSV с original_text, source_page, единицами и статусом парсинга; повторно прочитаны в типизированные объекты до расчета.')
        source_rows=[(key,r.get('original',r.get('copy','')),r.get('sha256',''),r.get('pages','DOCX')) for key,r in manifest.get('sources',{}).items()]
        if source_rows: table(3,'sources_inventory','Контроль источников',('Источник','Файл','SHA256','Страниц / формат'),source_rows,'Контрольные копии и их хеши сохранены в data и манифесте запуска. Изменения исходных документов обнаруживаются по SHA256.')
        input_rows=[]
        if inputs:
            changed={r['code']:r for r in data.get('scenario_inputs',()) if r['scenario']=='C'}
            keys={'capex_base','volume','fixed_opex','nwc','wacc','spread','volatility','gpr_base','igpr','gamma','nominal_tax',
                'inflation','subsidy_rate','approval','clawback','subsidy_year','equip_duty','duty_free','gov_rate','wht',
                'raw_base','logistics_in','input_duty','share_eu','share_asia','logistics_out','cbam','lead_days'}
            for row in inputs.provenance:
                if row['period_or_scenario']!='BASE' or row['parameter_id'] not in keys: continue
                key=row['parameter_id']; code=row['jurisdiction']; baseline=float(row['value'])
                scenario=changed.get(code,{}).get(key,baseline)
                input_rows.append((code+': '+key,f'{key}; PDF стр.{row["source_page"]}',baseline,scenario,row['unit']))
        table(3,'inputs_comparison','Исходные параметры: база и фрагментация',
            ('Параметр','Техническое имя / источник','Базовый сценарий','Сценарий 2','Единица'),input_rows,
            'Сценарий2 в этой таблице — В «Фрагментация и торговые войны». Проверены полнота, конечность чисел, единицы, диапазоны ставок, доли рынков и календарь. Все исходные значения сохранены; стрессовые экстремумы не удаляются. Полная таблица входов приведена в приложении.')
        take(3,'01')
        table(4,'architecture_flow','Поток выполнения',('Этап','Поток','Назначение'),[
            ('1','PDF → CSV → dataclass','Извлечение, происхождение, типизация и валидация'),
            ('2','DTO → Calculator → ResultDTO','Независимые математические вычисления'),
            ('3','Excel / тесты / Harness','Контроль формул, единиц, календаря и логики'),
            ('4','ResultDTO → таблица → график → DOCX','Анализ и воспроизводимое формирование отчетности')],
            'Один внешний запуск ApplicationInterface.run передает управление PipelineController. Формулы находятся в калькуляторах; генератор отчета получает уже рассчитанные DTO и не меняет финансовую модель.')
        take(4,'02')
        text(5,'Расчет ведется в USD по календарным годам от инвестиционного решения t=0. Базовый и сценарные наборы пересчитываются полностью. Обозначение GRP в задании сопоставлено с CRP. В качестве основной применяется экономически согласованная версия Parent CF; печатная версия PDF используется только для аудита.')
        for heading,selected in [('5.1. Основные показатели',{'RISK_CRP','RISK_GPR','RISK_RATE','NPV','IRR','PI','DPP','SCENARIO'}),
            ('5.2. Стоимостные и ресурсные показатели',{r[0] for r in FORMULAS}-{'RISK_CRP','RISK_GPR','RISK_RATE','NPV','IRR','PI','DPP','SCENARIO'})]:
            chapters[4].append(ReportHeadingDTO(heading))
            for r in FORMULAS:
                if r[0] in selected:
                    chapters[4].append(ReportFormulaDTO(r[0],r[1],VARIABLES[r[0]]+' '+r[2]+f'. Источник: задание, стр.{r[3]}; лекция7: {r[4]}. Класс: {r[5]}.'))
        metric_rows=[]
        for row in by_id.get('10',ReportSectionDTO('','','',None,(),(), '')).rows:
            name,npv,irr,pi,pvin,pvout,dpp=row
            metric_rows.extend([(name+' / NPV',npv,'млн USD','РАССЧИТАНО'),(name+' / IRR',irr,'%/год','РАССЧИТАНО' if isinstance(irr,(int,float)) else str(irr)),
                (name+' / PI',pi,'отношение','РАССЧИТАНО'),(name+' / DPP',dpp,'календарный год','НЕ ДОСТИГНУТО В ГОРИЗОНТЕ' if dpp=='NOT_REACHED' else 'РАССЧИТАНО')])
        table(6,'calculated_metrics','Сводные рассчитанные показатели',('Метрика','Значение','Единица измерения','Статус'),metric_rows,
            'Показатели рассчитаны для Local и Parent потоков отдельно. Если восстановление дисконтированных инвестиций не достигнуто к окончанию проекта, DPP не экстраполируется. Страновые факторы и годовые результаты раскрыты далее в связанных аналитических блоках.')
        for id in ('03','04','05','06','07','08','09','10','11'): take(6,id)
        text(7,'Harness Log фиксирует только фактически наблюдавшиеся дефекты. Проблемы учебного источника учитываются отдельно как SOURCE_ISSUE. Полный журнал — HARNESS_LOG.xlsx; ниже приведены карточки по структуре шаблона.')
        for issue in data.get('issues',()):
            if issue.get('kind')!='CODE_ERROR': continue
            table(7,'harness_'+issue['id'],'Карточка '+issue['id'],('Поле','Содержание'),[
                ('Запрос к ИИ / задача','Реализовать и проверить воспроизводимую финансовую модель/отчет'),
                ('Сгенерированный / изменённый фрагмент',issue.get('stage','')+'; '+issue.get('test',issue['id'])),
                ('Обнаруженная ошибка / галлюцинация',issue['observed']),('Причина',issue.get('cause','Причина и исправление зафиксированы в development_observations.json')),
                ('Как исправлено',issue['decision']),('Результат повторной проверки',issue.get('retest',issue.get('status','NOT_VERIFIED')))],
                'Карточка основана на наблюдении из журнала, а не на искусственно созданном дефекте. Статус повторной проверки берется из фактического протокола текущего запуска.')
        take(7,'20')
        test_rows=[(r['test_id'],'Проверка утверждений теста; подробности в tests.log',r.get('details') or 'Утверждения выполнены',r['status']) for r in data.get('tests',())]
        table(8,'test_protocol','Фактический протокол тестирования',('Тест / сценарий','Проверяемое свойство','Результат','Статус'),test_rows,
            'Тесты реально выполняются subprocess pytest в рамках одного pipeline. Численные проверки Excel и отсутствие кэша различаются по статусам; пропущенные проверки не объявляются успешными.')
        for id in ('12','13'): take(8,id)
        stress=by_id.get('13')
        rows=[]
        if stress:
            for name,baseline,scenario,delta,base_rate,stress_rate in stress.rows:
                rows.append((name+' Parent NPV',baseline,scenario,delta,delta/abs(baseline)*100 if baseline else 'Не определено','млн USD; предписанный стресс'))
        table(8,'stress_changes','Абсолютные и относительные изменения',
            ('Метрика','Базовый','Сценарный','Абс. изменение','Отн. изменение','Интерпретация'),rows,
            'Относительное изменение вычислено как Δ/|базовое значение|×100%, что сохраняет понятный знак при отрицательном NPV. Это представление уже рассчитанных значений, не новая финансовая модель.')
        for id in ('14','15'): take(8,id)
        text(9,'Визуализации встроены непосредственно после связанных таблиц в главах6 и8; аудит конфликтной формулы — в главе10. Это сохраняет последовательность «таблица → рисунок → анализ». Ниже приведены однофакторная чувствительность и реестр всех диаграмм.')
        take(9,'17')
        table(9,'chart_registry','Реестр визуализаций',('Код','Аналитический вопрос','Таблица-источник'),
            [(s.chart_id,s.title,s.table_id+'.csv') for s in sections if s.chart_id],
            'Численные проверки проверяют пределы осей, единицы и конечность координат. Фактический просмотр подтверждается SHA256 в docs/visual_review.json; статус текущего набора: '+manifest.get('visual_status','NOT_VERIFIED')+'. Проверенные календарные события — tables/chart_features.csv.')
        chapters[9].append(ReportHeadingDTO('10.1. Допущения модели'))
        table(10,'assumptions','Основные допущения',('Код','Допущение','Обоснование','Влияние'),[
            ('A01','Распределяется100% положительного operating CF','Payout ratio источником не задан','Parent CF и WHT'),
            ('A02','Cash tax≥0, перенос убытков не моделируется','Нет оснований для денежного возврата','Налог при EBIT<0'),
            ('A03','TV=0','Терминальная стоимость не задана','NPV и инвестиционный вывод'),
            ('A04','NWC фиксирован, не зависит от lead time','Прямое правило задания, стр.8','NWC и стресс Вьетнама'),
            ('A05','Три дискретных состояния A/Б/В','Вероятности заданы источником','Ожидание/σ не отражают весь риск'),
            ('A06','Учебные ставки PDF','Актуальное право не является предметом модели','Границы применимости')],
            'Каждое допущение раскрыто отдельно от исходного факта и покрыто проверками там, где оно влияет на расчетные тождества.')
        chapters[9].append(ReportHeadingDTO('10.2. Data Quality Report'))
        table(10,'data_quality','Контроль неоднозначностей источника',('Проблема','Параметр','Критичность','Влияние','Действие'),
            [(r['issue'],r['id']+'; PDF '+r['page'],'ВЫСОКАЯ' if r['id'] in ('SRC_WHT','SRC_NWC','SRC_NEG_TAX') else 'СРЕДНЯЯ',
                'Денежные потоки / сопоставимость методики',r['decision']) for r in SOURCE_ISSUES],
            'Критические неопознанные параметры останавливают расчет. Документируемые противоречия PDF не скрываются и не исправляются изменением входных значений без объяснения.')
        for id in ('16','18'): take(10,id)
        take(11,'19')
        text(11,'Границы применимости: модель не подтверждает юридическую распределяемость денежных средств, реальную доступность финансирования, валютный и технологический риск. Фиксированные цены и TV=0 заданы учебной постановкой. σ относится к дискретному набору сценариев и не является полным измерением инвестиционного риска.')
        for id in ('10','15','13','16'):
            if id in by_id: text(12,by_id[id].analysis,True)
        if '19' in by_id: text(12,by_id['19'].analysis,True)
        tests=data.get('tests',()); rec=data.get('reconciliation',())
        text(12,f'Проверка исполнения: тестов PASS — {sum(r["status"]=="PASS" for r in tests)}, FAIL — {sum(r["status"]=="FAIL" for r in tests)}; '
            f'Excel-сравнений PASS — {sum(r["status"]=="PASS" for r in rec)} из {len(rec)}. Итоговый статус запуска: {manifest.get("status","NOT_VERIFIED")}.',True)
        appendix=[]
        for s in sections:
            if s.section_id.startswith('П'): appendix.append(s); used.add(s.section_id)
            elif s.section_id not in used: chapters[5].append(s); used.add(s.section_id)
        result=[ReportChapterDTO(title,tuple(blocks)) for title,blocks in zip(titles,chapters)]
        if appendix: result.append(ReportChapterDTO('Приложение А. Полные годовые расчетные таблицы',tuple(appendix)))
        return result
