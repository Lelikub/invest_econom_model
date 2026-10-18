from pathlib import Path
import unicodedata


class SourceIssueService:
    def collect(self,p,m,s,rows,pdf_text,lecture_text,docs,logger):
        issues=[]
        def add(key,category,evidence,resolution,impact):
            issue=dict(id=key,category=category,evidence=evidence,resolution=resolution,impact=impact)
            issues.append(issue)
            logger.issue(key,'source review','Согласовать определения','docs/formula_registry.md',evidence,
                category,resolution,impact,category)
        normalized=unicodedata.normalize('NFKC',pdf_text)
        if 'При блокировке дивидендов' in normalized:
            start=normalized.index('При блокировке дивидендов')
            evidence='PDF 11: '+normalized[start:start+110].replace('\n',' ')
            add('debt_lockup_conflict','PDF source issue',evidence,
                'Основной режим сохраняет долг 39.39. literal_pdf отдельно показывает обнуление выплаты, задолженность не списывается.',
                'При налогах=0 остаток после выплаты 6.11 против 45.50 в буквальном режиме; разница 39.39, обязательство сохраняется.')
        if 'альфа Дженсена' in normalized:
            add('alpha_definition','PDF source issue','PDF 7: регрессия raw returns, перечень выходов называет α альфой Дженсена.',
                'alpha_raw рассчитана; alpha_jensen NOT_CALCULATED: месячная безрисковая история отсутствует.',
                'Свободный член raw OLS нельзя интерпретировать как подтверждённую Jensen alpha.')
        codes={r['parameter_code'] for r in rows}
        if 'taiwan' in codes and 'crp_taiwan' not in codes:
            add('taiwan_mapping','lecture ambiguity','PDF 4: GPR_Taiwan=2.50%; PDF 9 и лекция 29 используют CRP_Taiwan без отдельного значения.',
                'Явно отождествлены CRP_Taiwan=GPR_Taiwan; альтернатива без этой надбавки отражена в таблице чувствительности.',
                'В Ke добавляется 2.5 п.п.; в WACC — we_crisis*2.5 п.п.; Rf и beta используют GPR независимо.')
        if 'gamma2' not in codes:
            add('default_branch','missing input','Лекция 5, слайд 30: gamma2*DefaultSpread+Penalty; PDF 5 содержит только gamma1.',
                'DSCR<1 вызывает MissingDefaultParameters; тест подтверждает отказ от фиктивного числа.',
                'Обязательный сценарий DSCR=1.155 определён; более глубокий дефолт численно BLOCKED.')
        missing={'cash_taxes','depreciation','interest','principal','delta_nwc','dsra_target'}-codes
        if missing:
            add('waterfall_inputs','missing input','В таблицах 1–3 отсутствуют: '+', '.join(sorted(missing)),
                'Полный реальный водопад BLOCKED; иллюстрация taxes=0,NWC=0,revenue=150,OPEX=104.5, весь положительный остаток в DSRA при lockup.',
                'EBITDA=45.5 и договорной долг=39.39 известны; 6.11 — остаток до неизвестных налогов/резервов, а не подтверждённые дивиденды.')
        difference=p.ebitda/p.debt_service-p.dscr0
        if abs(difference)>1e-10:
            add('rounded_dscr','data anomaly',f'PDF 3: {p.ebitda}/{p.debt_service}={p.ebitda/p.debt_service:.12f}, задано {p.dscr0}.',
                'Основная стресс-формула использует заданный DSCR0; отдельно показан EBITDA/DebtService, допуск 0.0002x только для округлённого входа.',
                f'Исходная разница {difference:.9f}x; штраф и WACC рассчитаны по заданной, не переопределённой DSCR0.')
        add('capital_basis','economic modeling assumption','PDF 2–3 задаёт CAPEX и целевые веса, но не независимую рыночную стоимость Greenfield SPV.',
            'E0=450*0.65, D0=450*0.35 — условная начальная оценка для динамики; не балансовая оценка и не подтверждённая рыночная капитализация.',
            'Абсолютные E,D иллюстративны; WACC/рычаг/веса не зависят от общего масштаба V0.')
        add('tax_context','economic modeling assumption','PDF 2–3: номинальный налог 19%, R&D 4%, floor 15%.',
            'Учебные предпосылки, без утверждения о юридической доступности льготы; щит предполагает применимость вычета.',
            'Налоговая ставка WACC не определяет денежный налог waterfall.')
        add('currency_and_dates','economic modeling assumption','PDF 1–2: площадка в Польше; финансирование USD; таблица 3 — условные шоки осени 2026.',
            'Все ставки/потоки модели USD; сценарии не выдаются за новости. Нет смешения PLN-инфляции с USD FCF.',
            'Для реальной оценки нужны согласованные по валюте FCF и актуальные подтверждённые предпосылки.')
        add('investment_limits','missing input','PDF 12 требует сопоставить доходность отрасли; FCF, IRR и источник типовой доходности отсутствуют.',
            'NPV/IRR и численная типовая доходность не выдумываются; показаны факторы дисконтирования единичного потока за 10 лет.',
            'Можно оценить стоимость финансирования и направление риска, но нельзя доказать инвестиционную выгодность.')
        lines=['# SOURCE_ISSUES — фактически выявленные ограничения','']
        for issue in issues:
            lines.extend([f'## {issue["id"]} — {issue["category"]}',
                f'Доказательство: {issue["evidence"]}',f'Решение: {issue["resolution"]}',f'Влияние: {issue["impact"]}',''])
        (docs/'SOURCE_ISSUES.md').write_text('\n'.join(lines),encoding='utf-8')
        return issues
