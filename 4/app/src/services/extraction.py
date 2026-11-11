"""Text-layer and geometric PDF extraction. No financial calculations here."""
from pathlib import Path
import re
import unicodedata
import pymupdf
from ..io_utils import sha256, write_csv, write_json

COUNTRIES=('DEU','SRB','VNM')
NUM=r'[-+]?\d+(?:[.,]\d+)?'

def normalized(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip()

def match(pattern,text,group=1):
    found=re.search(pattern,normalized(text),re.I)
    if not found: raise ValueError(f'BLOCKED: unrecognized required PDF field: {pattern}; {normalized(text)[:180]}')
    return found.group(group)

def number(text): return float(match('('+NUM+')',text).replace(',','.'))
def percent(text): return float(match('('+NUM+r')\s*%',text).replace(',','.'))/100
def dollars(text): return float(match(r'\$([\d,]+(?:\.\d+)?)',text).replace(',',''))

# Parsing schema fixes field identity, not production values.
TABLE_SCHEMA={
    4:[('oecd',1,'index',number),('spread',2,'fraction',percent),('volatility',3,'ratio',number),('gpr_base',4,'fraction',percent)],
    5:[('igpr',1,'index',number),('gamma',2,'fraction/sigma',lambda t:number(t)/100),('nominal_tax',3,'fraction',percent)],
    6:[('inflation',1,'fraction',percent),('delay',2,'year',number),('subsidy_rate',3,'fraction',percent),('approval',4,'fraction',number),('clawback',5,'fraction',number)],
    7:[('subsidy_year',1,'year',lambda t:float(match(r'=\s*(\d+)',t))),('equip_duty',2,'fraction',percent),('duty_free',3,'indicator',number),('gov_rate',4,'fraction',percent),('wht',5,'fraction',percent)],
    10:[('raw_base',2,'USD/m2',dollars),('logistics_in',3,'fraction',percent),('lead_days',3,'day',lambda t:float(match(r'(\d+)\s*дн',t))),('input_duty',4,'fraction',percent),('raw_control',5,'USD/m2',dollars),('share_eu',6,'fraction',percent),('price_control',7,'USD/m2',dollars),('logistics_out',8,'fraction',percent),('outbound_days',8,'day',lambda t:float(match(r'(\d+)\s*дн',t)))],
    11:[('cbam',1,'fraction',percent),('net_price_control',2,'USD/m2',dollars)]}

class PdfExtractionService:
    def extract(self,pdf: Path,destination: Path):
        destination.mkdir(parents=True,exist_ok=True); self.rows=[]; self.source=Path(pdf).name
        with pymupdf.open(pdf) as doc:
            if len(doc)!=15: raise ValueError('BLOCKED: assignment must contain 15 pages')
            pages=[p.get_text() for p in doc]
            if any(len(x)<50 for x in pages): raise ValueError('BLOCKED: missing PDF text layer')
            (destination/'raw_pdf_text.txt').write_text('\n'.join(f'=== PAGE {i+1} ===\n{x}' for i,x in enumerate(pages)),encoding='utf-8')
            self.pages=pages; self.tables={}
            for page,schema in TABLE_SCHEMA.items():
                tables=doc[page-1].find_tables().tables
                if len(tables)!=1: raise ValueError(f'BLOCKED: table geometry page {page}')
                rows=tables[0].extract(); self.tables[page]=rows
                for key,row,unit,parser in schema:
                    for col,code in enumerate(COUNTRIES,1):
                        text=rows[row][col]
                        self.add(key,parser(text),unit,page,text,code,table='1' if page<9 else '2')
                if page==10:
                    for col,code in enumerate(COUNTRIES,1):
                        text=rows[6][col]; rates=re.findall('('+NUM+r')\s*%',normalized(text))
                        asia=float(rates[1])/100 if len(rates)>1 else 1-percent(text)
                        self.add('share_asia',asia,'fraction',page,text,code,table='2',notes='Complement only when PDF explicitly allocates 100% to EU')
            self.extract_project(); self.extract_timeline(); self.extract_taxes(); self.extract_scenarios()
            suppliers=[]
            for col,code in enumerate(COUNTRIES,1):
                suppliers.append(dict(jurisdiction=code,supplier=self.tables[10][1][col],source_page=10,source_file=self.source))
            write_csv(destination/'supplier_geography.csv',suppliers)
            write_json(destination/'pdf_tables.json',self.tables)
        groups={
            'project_constants.csv':lambda r:r['jurisdiction']=='ALL' and r['period_or_scenario']=='BASE',
            'jurisdiction_parameters.csv':lambda r:r['jurisdiction']!='ALL' and r['table_id']=='1' and r['parameter_id'] not in {'nominal_tax','subsidy_rate','approval','clawback','subsidy_year'},
            'subsidy_parameters.csv':lambda r:r['parameter_id'] in {'subsidy_rate','approval','clawback','subsidy_year'},
            'supply_chains.csv':lambda r:r['table_id']=='2' and not r['parameter_id'].startswith('share_'),
            'market_allocations.csv':lambda r:r['parameter_id'].startswith('share_'),
            'time_indexing.csv':lambda r:r['table_id']=='timeline',
            'tax_policies.csv':lambda r:r['table_id']=='tax' or r['parameter_id']=='nominal_tax',
            'scenarios.csv':lambda r:r['period_or_scenario']!='BASE'}
        for file,predicate in groups.items(): write_csv(destination/file,[r for r in self.rows if predicate(r)])
        keys=[(r['parameter_id'],r['jurisdiction'],r['period_or_scenario']) for r in self.rows]
        if len(keys)!=len(set(keys)): raise ValueError('Duplicate extraction keys')
        write_json(destination/'source_manifest.json',dict(source_file=str(pdf),sha256=sha256(pdf),pages=15,records=len(self.rows),schema='geometric-table/v1'))
        return self.rows

    def add(self,key,value,unit,page,text,country='ALL',period='BASE',table='text',notes=''):
        self.rows.append(dict(parameter_id=key,jurisdiction=country,period_or_scenario=period,value=value,unit=unit,
            original_text=normalized(text),source_file=self.source,source_page=page,table_id=table,parse_status='PARSED',notes=notes))

    def project(self,key,pattern,page,unit,parser=number):
        text=match(pattern,self.pages[page-1]); self.add(key,parser(text),unit,page,text)

    def extract_project(self):
        self.project('capex_base',r'Базовые капитальные затраты.*?=\s*(\$[\d,]+)',2,'USD',dollars)
        self.project('volume',r'Volume\s*=\s*([\d,]+)',2,'m2/year',lambda t:float(t.replace(',','')))
        self.project('fixed_opex',r'Базовые постоянные затраты:.*?(\$[\d,]+)',2,'USD/year',dollars)
        self.project('years',r'Горизонт промышленной эксплуатации: N\s*=\s*(\d+)',2,'year')
        self.project('nwc',r'Изменение чистого оборотного капитала:.*?(\$[\d,]+)',2,'USD',dollars)
        self.project('wacc',r'WACC.*?=\s*('+NUM+r'%)',3,'fraction',percent)
        self.project('igpr_mean',r'среднее.*?=\s*(\d+)',12,'index')
        self.project('igpr_sigma',r'стандартное отклонение.*?=\s*(\d+)',12,'index')
        self.project('pillar_floor',r'floor\s*=\s*('+NUM+r'%)',13,'fraction',percent)
        self.project('price_eu',r'Контрактная цена реализации:\s*(\$[\d.]+)',9,'USD/m2',dollars)
        self.project('price_asia',r'Рынок 2.*?Контрактная цена реализации:\s*(\$[\d.]+)',9,'USD/m2',dollars)

    def extract_timeline(self):
        text=normalized(self.pages[7])
        for code,name in [('SRB','Сербия'),('DEU','Германия')]:
            chunk=match(name+r' \(запуск.*?(эксплуатация длится с t = \d+ по t = \d+)',text)
            first,last=map(int,re.findall(r't = (\d+)',chunk))
            for key,value in [('first',first),('last',last),('first_load',1),('last_load',1)]:
                self.add(key,value,'fraction' if 'load' in key else 'year',8,chunk,code,table='timeline',notes='Full load explicitly stated in paragraph')
        vchunk=match(r'(Вьетнам \(запуск.*?Финансовый регламент)',text)
        first=int(match(r'начинается в году t = (\d+)',vchunk)); last=int(match(r'года t=(\d+)',vchunk))
        half=percent(match(r'составляет\s*('+NUM+r'%)',vchunk))
        for key,value in [('first',first),('last',last),('first_load',half),('last_load',half)]:
            self.add(key,value,'fraction' if 'load' in key else 'year',8,vchunk,'VNM',table='timeline')
        draw=match(r'(Сербия – в конце t =.*?Полный возврат)',text)
        release=match(r'(Сербия – в t =.*?Параметры сроков)',text)
        for code,name in [('SRB','Сербия'),('DEU','Германия'),('VNM','Вьетнам')]:
            for key,chunk in [('nwc_draw',draw),('nwc_release',release)]:
                val=int(match(name+r' – в (?:конце )?t = (\d+)',chunk))
                self.add(key,val,'year',8,chunk,code,table='timeline')
        self.add('calendar_end',max(r['value'] for r in self.rows if r['parameter_id']=='last'),'year',8,text,notes='Maximum final calendar year across the three extracted schedules')

    def extract_taxes(self):
        for i,code in enumerate(COUNTRIES,1):
            text=self.tables[5][4][i]
            rate=percent(match(r'CIT.*?=\s*('+NUM+r'%)',text)) if code=='VNM' else percent(self.tables[5][3][i])
            end=int(match(r't = \d+...(\d+)',text)) if code=='VNM' else max(r['value'] for r in self.rows if r['parameter_id']=='last')
            credit=dollars(match(r'т\.е\.\s*(\$[\d,]+)',text)) if code=='DEU' else dollars(match(r'и\s*(\$\d+)\s*для остальных',self.pages[12]))
            for key,value,unit in [('holiday_tax',rate,'fraction'),('holiday_end',end,'year'),('tax_credit',credit,'USD/year')]:
                self.add(key,value,unit,5 if key!='tax_credit' or code=='DEU' else 13,text,code,table='tax')

    def extract_scenarios(self):
        # Each value below is extracted from its source phrase, never supplied as a fallback.
        p14=normalized(self.pages[13]); p15=normalized(self.pages[14])
        specs=[('p_A',14,r'Глобальная интеграция.*?p\s*=\s*('+NUM+')','fraction',number),
            ('p_B',15,r'Status Quo.*?p\s*=\s*('+NUM+')','fraction',number),
            ('p_C',15,r'Фрагментация и торговые войны.*?p\s*=\s*('+NUM+')','fraction',number),
            ('integration_reduction',14,r'снижаются на\s*('+NUM+r'%)','fraction',percent),
            ('vnm_igpr',14,r'подскакивает до.*?=\s*(\d+)','index',number),
            ('vnm_freight',14,r'\(с 5% до\s*('+NUM+r'%)','fraction',percent),
            ('vnm_days',14,r'возрастает до\s*(\d+)\s*дн','day',number),
            ('srb_cbam',14,r'против Сербии в размере\s*('+NUM+r'%)','fraction',percent),
            ('deu_igpr_increase',15,r'Германия:.*?вырастает на\s*('+NUM+r'%)','fraction',percent),
            ('deu_inflation',15,r'с \+40% до\s*(\+?'+NUM+r'%)','fraction',percent)]
        for key,page,pattern,unit,parser in specs:
            text=match(pattern,p14 if page==14 else p15)
            self.add(key,parser(text),unit,page,text,period='SCENARIO',table='scenario')
