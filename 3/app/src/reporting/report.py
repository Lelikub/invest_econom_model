"""Academic Russian report, tied to computed data and audit records."""
from dataclasses import asdict
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import json
from docx import Document
from docx.shared import Pt,Cm,Inches
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from openpyxl import load_workbook
from PIL import Image

REPORT_NAME='Итоговый_отчет_ФИП_Практическая_3.docx'
ARCHIVE_NAME='Практическая_3_ФИП_результаты.zip'


def format_value(value):
    if value is None: return 'Не определено'
    if isinstance(value,bool): return 'Да' if value else 'Нет'
    if isinstance(value,float): return f'{value:.8g}'
    return str(value)


class WordReportWriter:
    def write(self,path,context):
        c=context; doc=Document()
        section=doc.sections[0]
        section.top_margin=section.bottom_margin=Cm(2)
        section.left_margin=Cm(2.5); section.right_margin=Cm(1.5)
        normal=doc.styles['Normal']; normal.font.name='Times New Roman'; normal.font.size=Pt(12)
        normal.paragraph_format.line_spacing=1.15
        for name in ('Heading 1','Heading 2','Title'):
            doc.styles[name].font.name='Times New Roman'
        footer=section.footer.paragraphs[0]; footer.alignment=1
        fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
        table_count=0
        def text(value): doc.add_paragraph(str(value))
        def table(title,headers,rows):
            nonlocal table_count
            table_count+=1; text(f'Таблица {table_count}. {title}')
            tab=doc.add_table(rows=1, cols=len(headers)); tab.style='Light Shading Accent 1'
            for cell,header in zip(tab.rows[0].cells,headers): cell.text=str(header)
            for row in rows:
                for cell,value in zip(tab.add_row().cells,row): cell.text=format_value(value)
            for row in tab.rows:
                for cell in row.cells:
                    for par in cell.paragraphs:
                        for run in par.runs: run.font.size=Pt(9)
            return tab
        def charts(ids):
            for row in c['charts']:
                if row['chart_id'] not in ids: continue
                doc.add_picture(str(c['output']/row['png_path']),width=Inches(6.1))
                text(row['caption']); text(row['interpretation'])
                text('Автоматическая проверка: '+row['validation_status']+'; отдельный визуальный просмотр: '+row['visual_status'])
                points=json.loads(row['annotated_points'])
                if points:
                    headers=list(dict.fromkeys(k for p in points for k in p))
                    table('Характерные точки '+row['chart_id'],headers,[[p.get(h,'') for h in headers] for p in points])
        doc.add_paragraph('РОССИЙСКИЙ ХИМИКО-ТЕХНОЛОГИЧЕСКИЙ УНИВЕРСИТЕТ\nимени Д. И. Менделеева',style='Title')
        text('Практическое занятие № 3 ФИП')
        doc.add_heading('Финансовый парсер, OLS-регрессия, стресс-WACC, ковенанты и Cash Flow Waterfall',0)
        text('Объект: AeroCarbon Synth, Кендзежин-Козле, Польша')
        text('Дата расчёта: '+c['manifest']['started_at'])
        text('Статус: '+c['status'])
        text('Документ сформирован программно; входные файлы, версии и проверки указаны ниже. Учебные шоки не являются утверждениями о реальных событиях.')
        doc.add_page_break()
        headings=['Цель и постановка задачи','Описание проекта','Источники и обозначения','PDF → CSV и контроль данных',
            'Архитектура программы','Этап 1. Базовая модель','Этап 2. Котировки и OLS','Этап 3. Граничные тесты',
            'Этап 4. Шесть взаимодействующих шоков','Этап 5. Ковенанты и каскад платежей',
            'Контроль графиков','Независимая верификация Python ↔ Excel','Harness Log и фактические исправления',
            'Инженерно-экономическое резюме','Заключение, ограничения и источники']
        doc.add_heading('Содержание',1)
        for i,title in enumerate(headings,1): text(f'{i}. {title}')
        p,m,s=c['inputs']; b=c['base'].metrics; st=c['stress'].metrics; r=c['regression']; wf=c['waterfall']; literal=c['literal']
        doc.add_heading('1. '+headings[0],1)
        text('Цель — воспроизводимо оценить стоимость USD-финансирования завода в спокойном рынке и связанном стресс-сценарии. Верификация отделяет программные ошибки от отсутствующих исходных данных. Неполные результаты не объявляются доказанными.')
        doc.add_heading('2. '+headings[1],1)
        text(f'Greenfield-завод полиакрилонитрильного прекурсора ({p.pan_capacity:,.0f} т/год) и углеродного волокна ({p.carbon_capacity:,.0f} т/год), Опольское воеводство. CAPEX={p.capex:.2f} млн USD; целевые веса {p.we:.0%}/{p.wd:.0%}. Производство энергоёмкое; проект финансируется в USD (PDF 1–3).')
        doc.add_heading('3. '+headings[2],1)
        table('Использованные файлы',['Файл','SHA256'],[(v['path'],v['sha256']) for v in c['manifest']['sources'].values()])
        text('Git: '+c['manifest']['commit']+'; ветка '+c['manifest']['branch']+'. Программа не меняет удалённую ветку.')
        text('Среда: '+json.dumps(c['manifest']['environment'],ensure_ascii=False))
        table('Обозначения',['Группа','Единицы'],[
            ('Rf,ERP,CRP,Ke,Kd,WACC,t','Доли единицы/год; в тексте при необходимости %'),
            ('beta,D/E,DSCR','Безразмерные; DSCR — кратность x'),('CAPEX,E,D,Revenue,OPEX,EBITDA,DebtService','млн USD'),
            ('Месячные доходности','Доли единицы за месяц, простая доходность'),('DF_t','USD текущей стоимости / 1 USD в году t')])
        doc.add_heading('4. '+headings[3],1)
        text('PyMuPDF извлекает все строки реальных таблиц 1–3, сохраняет raw_value,numeric_value,unit,source_page и SHA256. Каждый запуск повторно разбирает PDF; после записи CSV данные читаются заново в dataclass. OCR не потребовался. Исходный CSV цен копируется побайтно, хеши сверяются.')
        table('Исходные параметры',['Код','Исходная запись','Нормализовано','Единицы','PDF стр.'],[
            (row['parameter_code'],row['raw_value'],row['numeric_value'],row['unit'],row['source_page']) for row in c['parameters']])
        table('Аудит данных',['Проверка','Статус','Наблюдение'],[(v['check'],v['status'],v['details']) for v in c['audit']])
        text('Разница DSCR0 и EBITDA/DebtService отражает округление источника; не заменяет исходный DSCR0. Проверка adjusted close по одним ценам не доказывает учёт всех сплитов/дивидендов.')
        doc.add_heading('5. '+headings[4],1)
        text('ApplicationInterface → PipelineController → PdfExtractionService/DataRepository/MetricService/ScenarioService/ExcelService/TestService/Reporting → пассивные ProjectInputData, MarketAssumptions, ShockParameters и Result DTO. Сервисы используют отдельные классы Tax, Leverage, Hamada, CAPM, Debt, WACC, MonthlyReturns, OLS, Stress, Credit, DSCR, Waterfall, Discount. Калькуляторы не читают файлы и не строят графики.')
        text('Операционный журнал общий, с run_id и step_id; ошибки сохраняются append-only в JSONL. Протокол тестов и XML версионированы по run_id. История Harness Log не подменяется заранее придуманными ошибками.')
        text('Формулы и источники: docs/formula_registry.md; трассируемость: docs/requirements_traceability.md. По сравнению с заданиями 1–2 добавлены независимые калькуляторы, происхождение каждой величины, аудит временных рядов и контроль геометрии графиков.')
        doc.add_heading('6. '+headings[5],1)
        text('t_eff=max(t_nominal−R&D,t_floor); beta_U=beta_peer/[1+(1−t_peer)D_peer/E_peer]; beta_L=beta_U[1+(1−t_eff)D/E]; Ke=Rf+beta_L ERP+CRP; Kd=Rf+s_base; WACC=we Ke+wd Kd(1−t_eff). Формулы (1)–(7), PDF 5–6; лекция 5, слайды 6,15,17,19,29.')
        table('Базовые метрики',['Метрика','Значение','Единица'],[(k,v,c['units'][k]) for k,v in b.items()])
        text(f'Базовая WACC {b["wacc"]:.4%} — барьерная ставка для согласованного USD FCFF. Стоимость собственного капитала {b["ke"]:.4%}, долг после налога {b["kd_after_tax"]:.4%}. Налоговый щит применён ровно один раз.')
        charts(['04_rates'])
        doc.add_heading('7. '+headings[6],1)
        text(f'Предоставленный CSV: {len(c["prices"])} дневных пар. Месячная цена — последняя наблюдаемая дата месяца; календарь биржевых праздников отдельно не подтверждён. Последний неполный месяц исключается по правилу последнего буднего дня месяца. Начальный неполный месяц даёт только исходную цену на конец месяца; его частичная доходность не используется. Получено {len(c["monthly"])} месячных цен и {r.n} пар доходностей. Пропущенный месяц не превращается в доходность одного месяца; fillna(0) не применяется.')
        text('R_t=P_t/P_(t−1)−1; обязательная оценка scipy.stats.linregress(R_market,R_HXL). Месячная агрегация уменьшает микроструктурный шум, но сама по себе не доказывает устранение смещения неликвидности.')
        table('Результаты регрессии',['Показатель','Значение'],list(asdict(r).items()))
        delta=r.beta_ols-m.beta_peer
        text(f'Теоретическая beta={m.beta_peer:.4f}; эмпирическая beta={r.beta_ols:.6f}; знаковая разница {delta:+.6f}, абсолютная {abs(delta):.6f}, относительная {abs(delta)/abs(m.beta_peer):.2%}. Основной WACC использует теоретическую beta по заданию. Raw-intercept не является подтверждённой альфой Дженсена.')
        text('Ограничения OLS: согласованные общие месяцы, конечная выборка, выбросы сохранены. В ols_diagnostics.csv находятся остатки, leverage и leave-one-out beta; p-value и stderr опираются на допущения стандартной линейной регрессии, независимость и постоянство дисперсии не доказаны.')
        charts(['01_ols','02_prices','03_returns'])
        doc.add_heading('8. '+headings[7],1)
        text(f'Автоматически выполнено {len(c["tests"])} проверок, успешно {sum(v["passed"] for v in c["tests"])}. Все тесты включены в единую внешнюю команду.')
        table('Обязательные крайние случаи',['Тест','Вход','Ожидание','Факт','PASS'],[
            (v['test_id'],v['inputs'],v['expected'],v['actual'],v['passed']) for v in c['tests'] if v['test_id'].startswith('edge_')])
        text('Безналоговый тест t=0 проверяет изолированную формулу долга, а не модель с обязательным floor=15%. Негативные тесты охватывают NaN/Inf, схемы CSV, нулевые цены/капитал, константный benchmark, отсутствие дефолтных коэффициентов, отсутствующий Excel-движок, геометрию графиков и контролируемое завершение FAILED.')
        doc.add_heading('9. '+headings[8],1)
        text('В отличие от изолированной диагностики, обязательный сценарий одновременно включает все шесть шоков и сжатие EBITDA. Формулы (8)–(13): beta_U1=beta_U0[1+psi_tariff*tau+psi_energy*oil+psi_cross*tau*oil+psi_TW*GPR]; delta_total=crash+flight; Rf1=Rf0+eta*oil+term+alpha_cross*GPR; ERP1=ERP0+lambda*crash; CRP1=CRP0+Europe+Taiwan; DSCR1=DSCR0(1−mu). PDF 8–10 имеет приоритет над линейным вариантом лекции.')
        table('Базовый сценарий vs поликризис',['Метрика','База','Поликризис','Разность','Единица'],[
            (k,b[k],st[k],st[k]-b[k],c['units'][k]) for k in st])
        table('Декомпозиция изменения WACC',['Компонента','Изменение в долях'],[(v['component'],v['delta']) for v in c['decomposition']])
        text('Декомпозиция точная алгебраически, но зависит от фиксированного порядка переоценки ставок и весов; это не причинная атрибуция. Продукт пошлин и энергии сохранён. В ERP используется crash, в E используется delta_total. Изолированные сценарии имеют mu=0, поскольку источник не распределяет общее 30%-е сжатие EBITDA по шокам.')
        charts(['05_capital','06_credit','09_shocks'])
        doc.add_heading('10. '+headings[9],1)
        text(f'DSCR={st["dscr"]:.3f} < {p.covenant:.2f}; Dividend_Lockup={wf.dividend_lockup}. EBITDA кризиса={st["ebitda"]:.2f} млн USD. Контрактное обслуживание долга остаётся {p.debt_service:.2f} млн USD. Условие PDF об обнулении платежа при lockup раскрыто отдельно; основной режим его не применяет.')
        table('Известное и иллюстративное',['Показатель','Согласованный режим','Буквальный PDF'],[
            (k,getattr(wf,k),getattr(literal,k)) for k in ('debt_service','debt_paid','cfads_before_debt_service','cash_after_debt_service','dsra','dividends','retained','shortfall')])
        text('Основные известные величины: EBITDA1=45.5, договорной DebtService=39.39, остаток до налогов и резервов=6.11. Полный фактический waterfall BLOCKED: нет налогооблагаемой прибыли, амортизации, разбивки Interest/Principal, NWC и DSRA target. Иллюстративные допущения: выручка 150 неизменна, OPEX=150−EBITDA1, cash taxes=0, NWC=0, весь положительный остаток при lockup пополняет DSRA. Нулевой денежный налог — иллюстрация, а не налоговое заключение.')
        text('CFADS_before_debt_service и Cash_after_debt_service разделены. В буквальном режиме долг не выплачен, возникает shortfall=39.39; это демонстрирует финансовую несогласованность фразы источника, а не списание обязательства.')
        charts(['07_waterfall'])
        doc.add_heading('11. '+headings[10],1)
        table('Аудит визуализаций',['График','Автоаудит','Визуальный просмотр','Таблица'],[
            (v['chart_id'],v['validation_status'],v['visual_status'],v['dataset']) for v in c['charts']])
        text('Автоаудит проверяет конечность координат, габариты отображаемого текста и баланс waterfall; PNG открываются и проверяются на целостность при 210 dpi. Визуальный просмотр — отдельная запись, привязанная к SHA256 изображения; автоматический bbox-аудит не выдаётся за просмотр.')
        doc.add_heading('12. '+headings[11],1)
        text('Движок: '+c['excel_detail'])
        table('Независимая сверка',['Сценарий / метрика','Python','Excel','|Разность|','Статус'],[
            (v['scenario']+'/'+v['metric_id'],v['python_value'],v['excel_value'],v['abs_diff'],v['verification_status']) for v in c['reconciliation']])
        text('Формулы Excel ссылаются на исходные ячейки Inputs и промежуточные результаты. Python-значения находятся только в колонках сравнения. Кэш читается лишь после реального пересчёта; отсутствие движка или кэша даёт NOT_VERIFIED. rtol=1e-8, atol=1e-10; нулевые значения сравниваются абсолютным допуском.')
        doc.add_heading('13. '+headings[12],1)
        events=c['events']; latest={v['issue_id']:v for v in events}
        table('Фактически наблюдавшиеся ошибки и сомнения',['ID / категория','Наблюдение','Решение','Повторная проверка'],[
            (v['issue_id']+' / '+v['category'],v['issue'][:450]+('… Полный протокол в Harness Log.' if len(v['issue'])>450 else ''),
             v['resolution'],v['recheck']) for v in latest.values()])
        text('Подробности и вся история: HARNESS_LOG.xlsx и logs/events.jsonl. Ожидаемые RED-запуски TDD отмечены как этап разработки, а не как успешно пройденные проверки.')
        doc.add_heading('14. '+headings[13],1)
        text(f'В базе стоимость финансирования {b["wacc"]:.2%}, в поликризисе {st["wacc"]:.2%}. Рост ставки резко повышает требуемую доходность и снижает приведённую стоимость удалённых потоков. Для доказательства реализуемости нужны NPV/IRR на согласованном прогнозе USD FCFF. Типовая доходность химпроизводств и её проверенный источник не предоставлены, поэтому численное сопоставление с отраслью не выполняется.')
        table('Дисконтирование одного USD',['Год','База','Поликризис'],[(v['year'],v['base_factor'],v['stress_factor']) for v in c['discount']])
        charts(['08_discount'])
        text('Возможные инструменты поддержки в учебном сценарии: капитальная субсидия уменьшает требуемое финансирование; льготный USD-заём снижает спред; государственная гарантия может уменьшить кредитную премию; гарантированный заказ поддерживает EBITDA и DSCR. Это механизмы модели, не утверждение о доступности действующих программ. Энергосбережение и диверсификация поставок уменьшают операционную чувствительность. До расчёта эффекта нужны условия каждого инструмента и сценарий денежных потоков.')
        text(f'Порог ковенанты по сжатию EBITDA: mu*=1−{p.covenant}/{p.dscr0}={1-p.covenant/p.dscr0:.4%}. Исходный стресс {s.mu_ebitda:.0%} превышает порог. Нельзя оценивать выгодность завода только сравнением WACC без IRR/FCF.')
        doc.add_heading('15. '+headings[14],1)
        text('Итоговый статус: '+c['status']+'. Реализованные вычисления подтверждаются протоколами. Границы определимости исходников сохраняются: default spread, фактические taxes/NWC/DSRA, исторический Rf и IRR/FCF не заданы.')
        for issue in c['issues']: text(issue['id']+': '+issue['impact'])
        text('Источники: 1. Задание к практическому занятию 3 ФИП, стр. 1–12. 2. Лекция 5 ФИП, слайды 6,15,17–19,23,26–30. 3. Предоставленный hxl_gspc_adj_close_5y.csv, даты и SHA256 в манифесте. 4. Локальный клон https://github.com/Lelikub/invest_econom_model, указанный коммит; задания 1–2 использованы как архитектурные образцы. Внешние численные предпосылки не добавлялись.')
        path.parent.mkdir(parents=True,exist_ok=True); doc.save(path)
        return dict(sections=len(headings),tables=table_count,images=len(c['charts']))


class ArtifactValidationService:
    @staticmethod
    def render_review_pdf(docx,timeout=60):
        import subprocess
        import sys
        import pymupdf
        destination=docx.parent/'internal_review/report.pdf'
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('word_worker.py')),str(docx),str(destination)],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
            if result.returncode or 'WORD_RENDERED' not in result.stdout:
                return dict(status='NOT_VERIFIED',detail=(result.stderr or result.stdout)[-1000:])
            with pymupdf.open(destination) as pdf:
                outside=[]
                for i,page in enumerate(pdf):
                    for word in page.get_text('words'):
                        if word[0]<0 or word[1]<0 or word[2]>page.rect.width or word[3]>page.rect.height:
                            outside.append(dict(page=i+1,text=word[4]))
                return dict(status='PASS' if not outside else 'WARNING',pages=len(pdf),outside_page_text=outside,
                    path=str(destination.relative_to(docx.parent)))
        except (subprocess.TimeoutExpired,OSError) as exc:
            return dict(status='NOT_VERIFIED',detail=str(exc))

    @staticmethod
    def verify(output,charts):
        for name in ('Ground_Truth.xlsx','HARNESS_LOG.xlsx'):
            path=output/name
            if not path.is_file(): raise FileNotFoundError(path)
            wb=load_workbook(path,read_only=True,data_only=False)
            if not wb.sheetnames: raise ValueError('Empty workbook')
            wb.close()
        doc=Document(output/REPORT_NAME)
        if len(doc.inline_shapes)!=len(charts) or len(doc.tables)<10:
            raise ValueError('DOCX image/table integrity mismatch')
        if len([p for p in doc.paragraphs if p.style.name=='Heading 1'])<15:
            raise ValueError('DOCX required sections missing')
        for row in charts:
            with Image.open(output/row['png_path']) as img:
                if img.width<1500: raise ValueError('Low resolution chart')
                img.verify()
            if not (output/row['dataset']).is_file(): raise FileNotFoundError(row['dataset'])
        return dict(status='PASS',docx_images=len(doc.inline_shapes),docx_tables=len(doc.tables),charts=len(charts))

    @staticmethod
    def archive(app_dir,output):
        path=output/ARCHIVE_NAME
        with ZipFile(path,'w',ZIP_DEFLATED) as archive:
            for file in sorted(app_dir.rglob('*')):
                rel=file.relative_to(app_dir)
                if not file.is_file() or any(part in ('.venv','.pytest_cache','__pycache__','prior_outputs') or part.startswith('test_tmp_') for part in rel.parts): continue
                if file.suffix in ('.zip','.pyc'): continue
                archive.write(file,str(rel))
        with ZipFile(path) as archive:
            if archive.testzip() is not None: raise ValueError('Archive CRC failed')
            names=set(archive.namelist())
            for name in ('main.py','requirements.txt','README.md','run_manifest.json'):
                if name not in names: raise ValueError(f'Archive missing {name}')
        return dict(status='PASS',files=len(names),path=path.name)
