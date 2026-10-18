"""Extract actual ruled PDF tables, retain raw values and page provenance."""
import json
import re
import unicodedata
from pathlib import Path
import pymupdf
from ..io_utils import sha256, write_csv, write_json


PROJECT_LABELS = {
    'Капитальные вложения':'capex', 'Доля собственного капитала':'we',
    'Доля заемного капитала':'wd', 'Базовый финансовый рычаг':'de_control',
    'Номинальный налог на прибыль':'t_nominal', 'Налоговый вычет на НИОКР':'rd_relief',
    'Минимальный порог ОЭСР':'t_floor', 'Базовый кредитный спред':'s_base',
    'Базовый коэффициент покрытия долга':'dscr0', 'Банковская ковенанта безопасности':'covenant',
    'Базовая годовая выручка':'revenue', 'Базовые операционные затраты':'opex',
    'Базовая операционная прибыль':'ebitda', 'Годовой платеж по обслуживанию долга':'debt_service'}
MARKET_LABELS = {'Публичная компания-аналог':'peer','Рыночный бенчмарк':'index',
    'Глубина парсинга котировок':'horizon_years','Рыночная капитализация аналога':'equity_peer',
    'Финансовый долг аналога':'debt_peer','Налог на прибыль аналога':'tax_peer',
    'Безрисковая ставка США':'rf','Премия за риск рынка акций':'erp',
    'Базовая страновая премия Польши':'crp','Теоретическая рычаговая бета аналога':'beta_peer'}
SHOCK_LABELS = {'Шок 1: Ормузский пролив':'oil','Трансляция энергошока в инфляцию':'eta',
    'Энергоемкость технологии':'psi_energy','Шок 2: События вокруг Тайваня':'taiwan',
    'Сбой поставок тайваньских узлов':'psi_tw','Влияние дефицита ликвидности на долг':'alpha_cross',
    'Шок 3: Торговые пошлины США':'tariff','Тарифная эластичность затрат':'psi_tariff',
    'Коэффициент синергии пошлин и энергии':'psi_cross','Шок 4: Фискальный долг США':'term_premium',
    'Шок 5: Эскалация в Европе':'crp_europe','Региональный кредитный шок':'spread_europe',
    'Отток капитала из восточноевропейских активов':'flight','Шок 6: Обвал сектора High-Tech':'crash',
    'Коэффициент паники фондового рынка':'panic_lambda','Падение операционной прибыли':'mu_ebitda',
    'Штрафная эластичность кредита':'gamma1'}


def clean(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', text or '').split())


def normalize_number(raw: str) -> float:
    text=clean(raw).replace('−','-').replace('–','-')
    match=re.search(r'[+-]?\d(?:[\d ]*\d)?(?:[.,]\d+)?', text)
    if not match:
        raise ValueError(f'No numeric value: {raw!r}')
    value=float(match.group().replace(' ','').replace(',','.'))
    suffix=text[match.end():].lstrip()
    if suffix.startswith('%'):
        value/=100
    elif suffix.startswith('б.п.') or suffix.startswith('б. п.'):
        value/=10000
    return value


class PdfExtractionService:
    def extract(self, pdf: Path, data_dir: Path) -> list[dict]:
        data_dir.mkdir(parents=True, exist_ok=True)
        rows=[]; text_pages=[]
        with pymupdf.open(pdf) as doc:
            if len(doc)!=12:
                raise ValueError('Expected 12-page assignment; review changed PDF')
            for page_number,page in enumerate(doc,1):
                text_pages.append(page.get_text())
                if page_number not in (2,3,4,5):
                    continue
                for table in page.find_tables().tables:
                    for cells in table.extract()[1:]:
                        label=clean(cells[0])
                        for group,mapping in [('project',PROJECT_LABELS),('market',MARKET_LABELS),('shock',SHOCK_LABELS)]:
                            if label not in mapping:
                                continue
                            code=mapping[label]; raw=clean(cells[2])
                            numeric=None if code in ('peer','index') else normalize_number(raw)
                            unit=('text' if numeric is None else 'million USD' if 'млн' in raw else
                                  'fraction' if '%' in raw or 'б.п.' in raw else 'year' if code=='horizon_years' else 'ratio')
                            rows.append(dict(parameter_code=code,parameter_name=label,raw_value=raw,
                                numeric_value=numeric,unit=unit,source_file=pdf.name,source_page=page_number,
                                source_section={'project':'Таблица 1','market':'Таблица 2','shock':'Таблица 3'}[group],
                                scenario='stress' if group=='shock' else 'base',parsing_status='PASS',
                                notes=clean(cells[3]),group=group))
        expected=set(PROJECT_LABELS.values())|set(MARKET_LABELS.values())|set(SHOCK_LABELS.values())
        found=[r['parameter_code'] for r in rows]
        if len(found)!=len(set(found)) or set(found)!=expected:
            raise ValueError(f'PDF schema mismatch: missing {sorted(expected-set(found))}, duplicate keys {len(found)-len(set(found))}')
        context=clean(text_pages[1])
        name_match=re.search(r'Завод «([^»]+)»',context)
        capacities=re.search(r'прекурсора мощностью ([\d ]+) т/год и углеродного волокна конструкционного класса мощностью ([\d ]+) т/год',context)
        horizon=next(r for r in rows if r['parameter_code']=='horizon_years')
        month_match=re.search(r'\((\d+) месяцев\)',horizon['raw_value'])
        if not name_match or not capacities or not month_match:
            raise ValueError('Project name/capacity/month horizon missing from PDF')
        for code,label,raw,value,unit,group,page,section in [
            ('name','Название проекта',name_match.group(1),None,'text','project',2,'Пункт 1.2'),
            ('pan_capacity','Мощность ПАН-прекурсора',capacities.group(1)+' т/год',normalize_number(capacities.group(1)),'tonne/year','project',2,'Пункт 1.2'),
            ('carbon_capacity','Мощность углеродного волокна',capacities.group(2)+' т/год',normalize_number(capacities.group(2)),'tonne/year','project',2,'Пункт 1.2'),
            ('horizon_months','Горизонт анализа, месяцев',month_match.group(1)+' месяцев',float(month_match.group(1)),'month','market',horizon['source_page'],'Таблица 2')]:
            rows.append(dict(parameter_code=code,parameter_name=label,raw_value=raw,numeric_value=value,
                unit=unit,source_file=pdf.name,source_page=page,source_section=section,scenario='base',
                parsing_status='PASS',notes='Извлечено из фактического текста PDF',group=group))
        for group in ('project','market','shock'):
            write_csv(data_dir/f'{group}_parameters.csv',[r for r in rows if r['group']==group])
        write_json(data_dir/'source_manifest.json',dict(pdf_sha256=sha256(pdf),parameters=rows,
            project_context=[{'source_page':i+1,'raw_text':t} for i,t in enumerate(text_pages[:2])]))
        write_json(data_dir/'shock_keys.json',{f'shock_{i+1}':codes for i,codes in enumerate([
            ['oil','eta','psi_energy'],['taiwan','psi_tw','alpha_cross'],['tariff','psi_tariff','psi_cross'],
            ['term_premium'],['crp_europe','spread_europe','flight'],['crash','panic_lambda','mu_ebitda','gamma1']])})
        (data_dir/'assignment_text.txt').write_text('\n'.join(f'=== PAGE {i+1} ===\n{t}' for i,t in enumerate(text_pages)),encoding='utf-8')
        return rows
