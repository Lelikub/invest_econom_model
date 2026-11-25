from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from ..services.analysis import ids

TECH="Итоговый_отчет_ФИП_Практическая_5.docx"
MEMO="Доклад_руководству_ФИП_Практическая_5.docx"
SCRIPT="Текст_доклада_и_вопросы.docx"
NAVY="17364D"
TEAL="126788"


def nf(value,digits=2):
    if value is None:
        return "—"
    if abs(value)<.5*10**-digits:
        value=0
    return f"{value:,.{digits}f}".replace(","," ").replace(".",",")


def m(value,digits=3):
    return nf(value/1000,digits)


def shade(cell,color):
    sh=OxmlElement("w:shd")
    sh.set(qn("w:fill"),color)
    cell._tc.get_or_add_tcPr().append(sh)


class Word:
    def __init__(self,ch):
        self.ch=ch
        self.doc=Document()
        section=self.doc.sections[0]
        section.page_width=Cm(21); section.page_height=Cm(29.7)
        section.top_margin=Cm(1.65); section.bottom_margin=Cm(1.5)
        section.left_margin=Cm(2); section.right_margin=Cm(2)
        section.footer_distance=Cm(.65)
        normal=self.doc.styles["Normal"]
        normal.font.name="Times New Roman"
        normal.font.size=Pt(12)
        normal.paragraph_format.space_after=Pt(5)
        normal.paragraph_format.line_spacing=1.08
        for name,size in (("Title",26),("Heading 1",18),("Heading 2",13)):
            style=self.doc.styles[name]
            style.font.name="Times New Roman"; style.font.size=Pt(size)
            style.font.bold=True; style.font.color.rgb=RGBColor.from_string(NAVY)
        footer=section.footer.paragraphs[0]
        footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        footer.add_run("ФИП · Практическая работа № 5    ").font.size=Pt(9)
        field=OxmlElement("w:fldSimple")
        field.set(qn("w:instr"),"PAGE")
        footer._p.append(field)
        self.doc.core_properties.author="Учебный расчёт ФИП"

    def label(self,text):
        self.doc.add_heading(text,level=1)

    def title(self,text,subtitle=None):
        self.doc.add_heading(text,level=0)
        if subtitle:
            self.para(subtitle)

    def para(self,text):
        self.doc.add_paragraph(text)

    def table(self,headers,rows):
        table=self.doc.add_table(rows=1,cols=len(headers))
        table.style="Table Grid"
        for i,value in enumerate(headers):
            cell=table.rows[0].cells[i]
            shade(cell,NAVY)
            cell.text=str(value)
            for run in cell.paragraphs[0].runs:
                run.bold=True
                run.font.color.rgb=RGBColor.from_string("FFFFFF")
        table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        for index,row in enumerate(rows):
            for value,cell in zip(row,table.add_row().cells):
                cell.text="—" if value is None else str(value)
                if index%2==0:
                    shade(cell,"EDF4F6")
        for row in table.rows:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for cell in row.cells:
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                p=cell.paragraphs[0]
                p.paragraph_format.space_before=Pt(2)
                p.paragraph_format.space_after=Pt(2)
                p.paragraph_format.line_spacing=1.00
                for run in p.runs:
                    run.font.name="Times New Roman"; run.font.size=Pt(10.5)

    def figure(self,chart,caption,width=15.6):
        self.doc.add_picture(str(self.ch/f"{chart}.png"),width=Cm(width))
        pic=self.doc.paragraphs[-1]
        pic.alignment=WD_ALIGN_PARAGRAPH.CENTER
        pic.paragraph_format.keep_with_next=True
        p=self.doc.add_paragraph(caption)
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next=True
        p.paragraph_format.space_after=Pt(6)
        for run in p.runs:
            run.italic=True; run.font.size=Pt(9)

    def analysis(self,headers,rows,chart,caption,*paragraphs,width=15.6):
        self.table(headers,rows)
        self.figure(chart,caption,width)
        for p in paragraphs:
            self.para(p)

    def page(self):
        self.doc.add_page_break()

    def save(self,folder,name):
        self.doc.core_properties.title=name.removesuffix(".docx").replace("_"," ")
        self.doc.save(folder/name)


def production_rows(op,r,gross):
    return [(p.code,nf(p.yield_rate,2),nf(p.margin,0),nf(x),nf(raw))
            for p,x,raw in zip(op.products,r.x,gross)]


def portfolio_rows(*pairs):
    return [(name,ids(r),nf(r.capex,0),nf(r.npv,1),r.score,nf(r.slack,0)) for name,r in pairs]


PF_HEADER=("Вариант","Проекты ID","CAPEX, млн","NPV, млн","MCDA","Остаток, млн")
PROD_HEADER=("Продукт","Выход годного","Маржа, тыс./т","Годный выпуск, т","Валовый запуск, т")


class ReportService:
    def __init__(self,folder,template):
        self.folder=folder
        self.ch=folder/"charts"
        self.template=template

    def technical(self,d):
        w=Word(self.ch)
        op,pf,sc=d["op"],d["pf"],d["sc"]
        base,stress,pareto,edges=d["base"],d["stress"],d["pareto"],d["edges"]
        lp,milp,fixed=base["lp"],base["milp"],base["fixed"]
        exact,greedy=base["exact"],base["greedy"]
        if self.template:
            source=Document(self.template)
            cover=[p.text for p in source.paragraphs if p.text][:8]
            for line in cover:
                p=w.doc.add_paragraph(line)
                p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        w.title("Практическая работа № 5",
                "MILP-оптимизация производственной программы и формирование инвестиционного портфеля на основе границы Парето")
        w.para("Курс «Финансовое и технико-экономическое обоснование проектов в химической и машиностроительной отраслях»")
        w.para("Завод специальной химии и конструкционных полимеров · квартальный операционный план и трёхлетняя инвестиционная программа")
        w.para("Студент ____________________    Группа __________    2026")
        w.doc.add_heading("Цель и объект",2)
        w.para("Определить объёмы кондиционного выпуска при ограничениях оборудования и сырья, выбрать инвестиции при рационировании капитала и оценить цену роста надёжности. Завод выпускает электролит аккумуляторного класса, фторполимерное связующее и конструкционный компаунд.")
        w.para(f"Результат производственного расчёта составил {m(milp.objective,1)} млн руб. за квартал. Финансовый портфель {ids(exact)} даёт {nf(exact.npv,0)} млн руб. NPV при бюджете {nf(pf.budget,0)} млн руб.")
        w.page()

        w.label("1. Исходные данные и технологические нормы")
        w.para("Исходные показатели извлечены из текстового слоя задания. CSV содержит номер страницы, исходный токен, число после нормализации и единицу. При повторной загрузке контролируются полнота, размерности, связи и контрольные значения.")
        machine_rows=[(f"Агрегат {i}",*(nf(a) for a in row),nf(r.capacity,0),nf(r.fixed_cost,0))
                      for i,(r,row) in enumerate(zip(op.machines,op.machine_coefficients),1)]
        material_rows=[(label,*(nf(a) for a in row),f"{nf(r.capacity,0)} {r.unit}","—")
                       for label,r,row in zip(("NMP","Наномодификатор"),op.materials,op.material_coefficients)]
        w.analysis(("Ресурс","Э-1","П-2","К-3","Квартальный фонд","Пуск, тыс. руб."),
                   machine_rows+material_rows,"effective","Рис. 1. Приращение нормы П-2 на тонну готовой продукции. effective.csv.",
                   f"Эффективные нормы равны сырьевым нормам, делённым на выход годного. При Y₂ = {nf(op.products[1].yield_rate)} тонна П-2 требует дополнительно {', '.join(nf(v) for v in d['extra_p2'])} маш.-ч на агрегатах 1–3 соответственно.",
                   "В базовом оптимуме П-2 отсутствует. Удельное приращение характеризует технологию П-2, а его фактическая дополнительная квартальная загрузка при данном плане равна нулю.")
        w.para("Нормы оборудования даны в маш.-ч/т сырого запуска, NMP в л/т, наномодификатора в кг/т. Маржа дана в тыс. руб./т кондиционного выпуска и учитывает исходные расходы на брак.")
        w.page()

        w.label("2. Линейная релаксация и режимы пуска")
        w.para("Переменные xⱼ описывают кондиционный выпуск, yₖ — пуск. xgross = x/Y. Ограничения имеют вид Σ aₖⱼxⱼ/Yⱼ ≤ bₖyₖ и Σ gᵣⱼxⱼ/Yⱼ ≤ Bᵣ. Цель max Σ cⱼxⱼ − Σ Fₖyₖ. Плотная поэлементная константа bₖYⱼ/aₖⱼ существует при aₖⱼ > 0. В модели используются агрегированные строки с bₖ.")
        w.analysis(("Модель","Э-1, т","П-2, т","К-3, т","Флаги пуска","Прибыль, млн"),
                   [(label,*(nf(x) for x in r.x)," / ".join(nf(y,3) for y in r.y),m(r.objective))
                    for label,r in (("LP",lp),("MILP",milp),("Fixed LP",fixed))],
                   "operations","Рис. 2. Прибыль LP, MILP и Fixed LP. operations.csv.",
                   f"LP разрешает дробные пуски и завышает прибыль на {nf(d['lp_premium'])} тыс. руб. Целочисленная модель открывает три агрегата. Верхняя граница HiGHS составляет {nf(milp.bound)} тыс. руб., зазор {nf(milp.gap,6)}. Оптимум подтверждён перебором восьми режимов пуска и PuLP/CBC.",
                   "После фиксации y условия двойственности проверены на непрерывной модели. Разность правой части и фактической загрузки сопоставляется с доступным физическим фондом.")
        w.page()

        w.label("3. Производственная программа")
        w.analysis(PROD_HEADER,production_rows(op,milp,d["gross"]),"production",
                   "Рис. 3. Кондиционный и валовый выпуск, физическая загрузка. production.csv, resources.csv.",
                   f"К выпуску приняты Э-1 ({nf(milp.x[0])} т) и К-3 ({nf(milp.x[2])} т). Квоты сырья исчерпываются. Все агрегаты имеют резерв физического времени.",
                   "Пуск агрегатов связан с технологическими маршрутами включённых продуктов. Дробные доли LP описывают экономию в релаксации и не задают рабочий график агрегатов.")
        w.doc.add_heading("Воспроизводимость",2)
        w.para("Интерфейс передаёт управление контроллеру. Сервис извлечения создаёт CSV, репозиторий пересобирает неизменяемые DTO, валидация допускает их к расчёту. Фасад ProductionAndPortfolioOptimizer делегирует LP/MILP и Knapsack профильным решателям.")
        w.page()

        w.label("4. Узкие места и проверка двойственности")
        labels=("Агрегат 1","Агрегат 2","Агрегат 3","NMP","Наномодификатор")
        w.analysis(("Ресурс","Ед.","Факт","Остаток Fixed LP","λ Fixed LP, тыс./ед.","λ LP, тыс./ед."),
                   [(label,unit,nf(load),nf(slack),nf(a,3),nf(b,3)) for label,unit,load,slack,a,b in
                    zip(labels,("маш.-ч",)*3+("л","кг"),fixed.load,fixed.slack,fixed.shadow,lp.shadow)],
                   "duals","Рис. 4. Загрузка и теневые цены Fixed LP. resources.csv.",
                   f"NMP и наномодификатор ограничивают прибыль. Их локальные оценки при фиксированных пусках равны {nf(fixed.shadow[3],0)} тыс. руб./л и {nf(fixed.shadow[4],0)} тыс. руб./кг. Нулевой выпуск П-2 сопровождается RC = {nf(fixed.reduced[1],0)} тыс. руб./т в Fixed LP и {nf(lp.reduced[1])} тыс. руб./т в релаксации.",
                   "В LP-релаксации машинные строки связывают нагрузку с дробным пуском. Их положительные оценки относятся к правым частям этих строк. В Fixed LP машинные фонды свободны, а их оценки равны нулю.",
                   "Для обеих LP проверены сильная двойственность, λ·slack и x·RC. Знак RC принят как c−Aᵀλ. Теневые цены действуют локально при данной структуре модели.")
        w.page()

        w.label("5. Рюкзак, индексы PI и проверка Excel")
        w.para("Отбор максимизирует ΣNPVᵢzᵢ при ΣCAPEXᵢzᵢ≤B. Связи задаются как z₂+z₃≤1, z₄≤z₁ и z₅=z₇. Жадный проход ранжирует по PI=1+NPV/CAPEX и добавляет обязательные проекты до проверки набора.")
        w.analysis(PF_HEADER,portfolio_rows(("Жадный PI",greedy),("Knapsack MILP",exact),("Полный перебор",base["enumeration"]),("Контроль",base["control"])),
                   "portfolio","Рис. 5. Инвестиции и чистая приведённая стоимость по методам. portfolio_comparison.csv.",
                   f"Полный перебор проверил {pareto['examined']} комбинаций. Допустимы {len(pareto['feasible'])}. Жадный алгоритм уступает оптимуму {nf(d['greedy_loss'],0)} млн руб. NPV. У MILP верхняя граница {nf(exact.bound,0)} млн руб., зазор {nf(exact.gap,6)}.",
                   f"Ground_Truth.xlsx содержит {d['excel_checks']} подтверждённых сопоставлений Excel. Статус Excel — {d['excel']['status']}. Зафиксированы {d['numeric_checks']} независимых численных сверок. Reconciliation.csv хранит исходные значения, отклонения и допуски.")
        w.para("Книга включает формульный перебор All128 и отдельные листы LP, MILP и Fixed LP. Если доступны нативные отчёты Solver, их листы и статус сохранены в manifest и книге.")
        w.page()

        w.label("6. Граничные случаи и Harness Log")
        edge_rows=[(r["case"],r["status"],m(r["objective"]) if r["objective"] is not None else "—",
                   (" / ".join(nf(r[k]) for k in ("x1","x2","x3")) if r["x1"] is not None else r["ids"]),
                   nf(r["rc1"])) for r in edges]
        w.analysis(("Проверка","Статус","Прибыль, млн","Выпуск, т / ID","RC Э-1"),edge_rows,
                   "edges","Рис. 6. Прибыль в производственных граничных случаях. edge_cases.csv.",
                   f"При нулевом NMP допустим нулевой план. Отрицательная маржа Э-1 даёт нулевой выпуск и RC {nf(edges[1]['rc1'])} тыс. руб./т в Fixed LP. При отключении агрегата 3 остаётся {nf(edges[2]['x1'])} т Э-1. NMP используется в объёме {nf(edges[2]['nmp_load'],0)} л, загрузки первых двух агрегатов составляют {nf(edges[2]['m1_load'])} и {nf(edges[2]['m2_load'])} маш.-ч.",
                   f"При добавлении связи 1–4 проект 4 исключается, а портфель {edges[3]['ids']} остаётся допустимым. Пройдено {d['observed_tests']} тестов. Harness Log хранит условия, найденные ошибки, исправления, повторные проверки и отклонения источника.")
        w.page()

        w.label("7. Граница Парето и цена надёжности")
        unsupported=", ".join(ids(p) for p in d["unsupported"]) or "нет"
        skipped=", ".join(ids(p) for p in d["skipped"]) or "нет"
        w.analysis(("Проекты","CAPEX, млн","NPV, млн","MCDA","ε-сетка","Взвешенная сумма"),
                   [(ids(p),nf(p.capex,0),nf(p.npv,0),p.score,"Да" if (p.npv,p.score) in pareto["epsilon_points"] else "Нет",
                     "Да" if (p.npv,p.score) in pareto["supported"] else "Нет") for p in pareto["frontier"]],
                   "pareto","Рис. 7. Допустимое множество, истинный фронт, ε-сетка и взвешенная сумма. pareto_*.csv.",
                   f"Границы сетки по достижимому MCDA — {pareto['ranges'][2]} и {pareto['ranges'][3]}, шаг {sc.epsilon_step}. По сравнению с истинным фронтом пропущены ε-сеткой — {skipped}, нормированной взвешенной суммой — {unsupported}. Для весов проверены точки смены оптимума, промежутки и совпадающие оптимумы.",
                   "Взвешенная сумма α·NPVнорм + (1−α)·MCDAнорм использует min–max по допустимому множеству. Из равных по баллу решений берётся вариант с максимальным NPV. При равном NPV для ε-сетки выбран вариант с большим MCDA.")
        w.page()

        w.label("8. MRT и выбор точки компромисса")
        rows=[(f"{r['from_score']} → {r['to_score']}",nf(r["npv_loss"],0),r["score_gain"],nf(r["mrt"],3),
               "Да" if r["efficient"] else "Нет") for r in pareto["mrt"]]
        knee=d["knee"]
        interpretation=(f"Колено — {knee['ids']}, NPV {nf(knee['npv'],0)} млн руб., MCDA {knee['score']}. "
                        f"Поворот в нормированных координатах равен {nf(knee['angle_100'],1)}°. "
                        "Максимум сохраняется при масштабе NPV 0,8 и 1,25."
                        if knee else "По принятой проверке устойчивости выделить колено нельзя.")
        w.analysis(("Шаг по MCDA","Потеря NPV, млн","Прирост","MRT, млн/балл","MRT < 0,5"),rows,
                   "mrt","Рис. 8. Предельная норма трансформации истинного фронта. mrt.csv, knee.csv.",
                   interpretation,
                   f"MRT = |ΔNPV/ΔMCDA| для соседних точек с ΔMCDA > 0. Критерий эффективного размена — MRT < {nf(sc.mrt_limit,1)} млн руб. на балл. "
                   f"На этом фронте MRT лежит в диапазоне {nf(min(r['mrt'] for r in pareto['mrt']),3)}–"
                   f"{nf(max(r['mrt'] for r in pareto['mrt']),3)}. Издержки надёжности возрастают после колена и остаются ниже порога во всех показанных переходах.")
        w.page()

        w.label("9. Финансовый и регуляторный стресс")
        finance,green=stress["finance"],stress["green"]
        w.analysis(PF_HEADER,portfolio_rows(("База",exact),("Секвестр",finance),("MCDA ≥ 280",green)),
                   "stress_portfolio","Рис. 9. NPV и MCDA при секвестре и требовании надёжности. stress_portfolio.csv.",
                   f"Секвестр сокращает бюджет до {nf(sc.stress_budget,0)} млн руб. и NPV каждого проекта на {nf(sc.npv_cut*100,0)}%. "
                   f"Выбираются проекты {ids(finance)}. Из базы исключён проект {', '.join(map(str,d['finance_removed']))}. "
                   f"Падение NPV составляет {nf(d['finance_loss'])} млн руб., из них {nf(d['finance_budget_loss'],0)} млн из-за смены состава и {nf(d['finance_shock_loss'])} млн из-за снижения NPV сохранённых проектов. Обязательные связи соблюдены.",
                   f"Порог {sc.score_floor} баллов допускает {d['green_options']} портфеля. Оптимальный вариант {ids(green)} добавляет {d['green_score_gain']} баллов относительно базы за {nf(stress['green_npv_loss'],0)} млн руб. NPV.")
        w.page()

        w.label("10. Углеродный налог и пределы оценки")
        w.analysis(("Продукт","Выпуск, т","Отходы, т","Δ маржи, тыс./т","Выбросы, т CO₂","Налог, тыс."),
                   [(r["product"],nf(r["carbon_output"]),nf(r["carbon_waste"]),nf(r["delta_margin"],3),
                     nf(r["emissions"]),nf(r["tax_paid"])) for r in stress["carbon_rows"]],
                   "stress_carbon","Рис. 10. Начисление налога по продуктам. stress_operations.csv, stress_profit.csv.",
                   f"При ставке {nf(sc.carbon_tax,0)} руб./т CO₂ и факторе {nf(sc.emission_factor,1)} т CO₂/т отхода вычет из удельной маржи равен T·e·(1/Y−1)/1000. "
                   f"План выпуска сохраняется. Прибыль падает на {nf(stress['carbon_profit_loss'])} тыс. руб. до {m(stress['carbon'].objective)} млн руб. за квартал.",
                   "В инвестиционном контуре NPV проектов остаются исходными. Строгий порог MCDA задаётся прямым ограничением. Для оценки влияния проектов на выпуск и выбросы нужны сценарии по технологическим параметрам и денежным потокам.")
        w.doc.add_heading("Решение для инвестиционного комитета",2)
        w.para(f"При цели максимума NPV подходит {ids(exact)}. Для роста надёжности при заданном минимуме {sc.score_floor} баллов подходит {ids(green)}. "
               "Перед утверждением программы следует подтвердить стабильность сырьевых поставок и организовать совместное финансирование проектов 5 и 7 при выборе экологического кластера.")
        w.doc.add_heading("Источники и приложения",2)
        w.para("Г. Г. Потапов. Задание 5, стр. 1–9. Лекция 9 ФИП, слайды 5–10, 12–27 и 28–35. Приложения к расчёту содержатся в data, docs, output/tables, Ground_Truth.xlsx и HARNESS_LOG.xlsx.")
        w.page()
        w.label("Приложение. Реестр инвестиционных проектов")
        w.table(("ID","Инициатива","CAPEX, млн","NPV, млн","MCDA"),
                [(p.id,p.name,nf(p.capex,0),nf(p.npv,0),p.score) for p in pf.projects])
        w.para("Источник исходных данных — задание, стр. 4. В книге Ground_Truth.xlsx лист Projects содержит значения реестра, лист PI — формулы индексов, а лист All128 — формульные проверки бюджета и связей.")
        w.save(self.folder,TECH)

    def memo(self,d):
        w=Word(self.ch)
        base,sc,stress=d["base"],d["sc"],d["stress"]
        p=base["milp"]; exact=base["exact"]; green=stress["green"]; fin=stress["finance"]
        w.title("Докладная записка", "Инвестиционному комитету · производственный квартал и трёхлетняя модернизация")
        w.label("1. Выпуск и сырьё")
        w.analysis(PROD_HEADER,production_rows(d["op"],p,d["gross"]),"production","Квартальный выпуск и загрузка оборудования.",
                   f"Утвердить выпуск {nf(p.x[0])} т Э-1 и {nf(p.x[2])} т К-3 при квартальной прибыли {m(p.objective,1)} млн руб. Для этого работают все три агрегата.",
                   f"NMP и наномодификатор используются полностью. В пределах локальной оценки дополнительный литр NMP даёт до {nf(base['fixed'].shadow[3],0)} тыс. руб., килограмм наномодификатора — до {nf(base['fixed'].shadow[4],0)} тыс. руб. Поставки этих ресурсов определяют устойчивость плана.")
        w.para("При остановке экструдера запланировать отдельный режим выпуска Э-1. Сохранять квоты сырья и контроль выхода годного в квартальном мониторинге.")
        w.page()

        w.label("2. Выбор портфеля и цена баллов")
        front=[(f"MCDA {r.score}",r) for r in d["pareto"]["frontier"]]
        w.analysis(PF_HEADER,portfolio_rows(*front),"pareto","Финансово-инженерный компромисс между четырьмя решениями.",
                   f"При финансовой цели выбрать {ids(exact)} с NPV {nf(exact.npv,0)} млн руб. и остатком {nf(exact.slack,0)} млн руб. "
                   f"При пороге {sc.score_floor} баллов выбрать {ids(green)}. Цена перехода — {nf(stress['green_npv_loss'],0)} млн руб. NPV за {d['green_score_gain']} дополнительных баллов.",
                   (f"Если порог гибкий, точка компромисса {d['knee']['ids']} даёт {d['knee']['score']} баллов при NPV {nf(d['knee']['npv'],0)} млн руб. и полном освоении бюджета."
                    if d["knee"] else "Устойчивое колено при проверке масштабов не выявлено."))
        w.page()

        w.label("3. Действия при стрессе")
        w.analysis(PF_HEADER,portfolio_rows(("База",exact),("Секвестр",fin),("Порог MCDA",green)),
                   "stress_portfolio","Портфель при бюджетном и регуляторном давлении.",
                   f"При секвестре до {nf(sc.stress_budget,0)} млн руб. оставить проекты {ids(fin)}. NPV составит {nf(fin.npv,1)} млн руб., незанятый бюджет — {nf(fin.slack,0)} млн руб. "
                   "При действии регуляторного порога одновременно обеспечить финансирование проектов 5 и 7.",
                   f"Углеродный налог сокращает квартальную прибыль на {nf(stress['carbon_profit_loss'])} тыс. руб. Выпуск Э-1 и К-3 сохраняется. "
                   "Для производственного бюджета достаточно учесть фактическую массу отходов и ставку сценария.")
        w.para(f"Контроль решения выполнен двумя решателями и полным перебором. Пройдено {d['observed_tests']} тестов. Статус сверки Excel — {d['excel']['status']}.")
        w.save(self.folder,MEMO)

    def script(self,d):
        w=Word(self.ch)
        base,stress,sc=d["base"],d["stress"],d["sc"]
        p=base["milp"]; exact=base["exact"]; fin=stress["finance"]; green=stress["green"]
        w.title("Защита перед инвестиционным комитетом","Сценарий выступления и ответы на вопросы · Практическая работа № 5")
        messages=[
            ("Решение комитета",f"Квартальный выпуск и трёхлетняя программа имеют разные цели. Производственный план даёт {m(p.objective,1)} млн рублей за квартал. Финансовый портфель {ids(exact)} добавляет {nf(exact.npv,0)} млн рублей NPV."),
            ("Производство",f"План предусматривает {nf(p.x[0])} т Э-1 и {nf(p.x[2])} т К-3. Нормы пересчитаны на кондиционную тонну. NMP и наномодификатор являются узкими местами. Их теневые цены рассчитаны при фиксированных пусках."),
            ("Цена инженерной надёжности",f"Из {d['pareto']['examined']} комбинаций допустимы {len(d['pareto']['feasible'])}. Истинный фронт содержит {len(d['pareto']['frontier'])} решения. "
             f"На переходе к порогу {sc.score_floor} баллов NPV падает на {nf(stress['green_npv_loss'],0)} млн рублей относительно финансового оптимума."),
            ("Стрессы",f"При бюджете {nf(sc.stress_budget,0)} млн и снижении индивидуальных NPV выигрышный набор {ids(fin)} даёт {nf(fin.npv,1)} млн рублей NPV. "
             f"Углеродный налог уменьшает операционную прибыль на {nf(stress['carbon_profit_loss'])} тыс. рублей. Для экопорога выбирается {ids(green)}."),
            ("Предложение к утверждению",f"Если действует минимум {sc.score_floor} баллов, утвердить {ids(green)} и совместное финансирование 5 и 7. При финансовом приоритете оставить {ids(exact)}. Зафиксировать условия пересмотра при ухудшении поставок сырья."),
        ]
        for i,(title,body) in enumerate(messages,1):
            w.doc.add_heading(f"{i}. {title} · 35–45 секунд",2)
            w.para(body)
        w.page()
        w.label("Вопросы финансового директора и технолога")
        for title,body in [
            ("Почему результат по PI уступает решателю?",
                f"PI сортирует проекты по относительной доходности. Бюджет и связи ограничивают комбинации. Допустимый жадный набор {ids(base['greedy'])} уступает {nf(d['greedy_loss'],0)} млн рублей NPV. Перебор и два решателя подтверждают максимум."),
            ("Как обосновать цену экопорога?",
                f"Максимум при {sc.score_floor} баллах имеет NPV {nf(green.npv,0)} млн. Разность от финансового оптимума составляет {nf(stress['green_npv_loss'],0)} млн за {d['green_score_gain']} баллов. В денежном плане оценка относится к заданным NPV."),
            ("Откуда взялись новые финансовые условия?",
                f"Мы применили сокращение бюджета до {nf(sc.stress_budget,0)} млн и единый множитель NPV {nf(1-sc.npv_cut)}. Для самостоятельного пересчёта ставки потребуются денежные потоки проектов."),
            ("Почему П-2 исключён при положительной марже?",
                f"Приведённая стоимость в Fixed LP равна {nf(base['fixed'].reduced[1],0)} тыс. руб./т. Норма сырья при выходе {nf(d['op'].products[1].yield_rate)} делает текущую маржу недостаточной для покрытия альтернативной стоимости ресурсов."),
            ("Что произойдёт при остановке экструдера?",
                f"Выпуск П-2 и К-3 прекращается. Остаточный оптимум выпускает {nf(d['edges'][2]['x1'])} т Э-1 и даёт {m(d['edges'][2]['objective'])} млн руб. за квартал."),
            ("Сколько стоит запас сырья?",
                f"При фиксированных пусках локальная оценка составляет {nf(base['fixed'].shadow[3],0)} тыс. руб. за литр NMP и {nf(base['fixed'].shadow[4],0)} тыс. руб. за килограмм наномодификатора. При крупных изменениях квот модель следует решить заново."),
        ]:
            w.doc.add_heading(title,2); w.para(body)
        w.save(self.folder,SCRIPT)

    def run(self,d):
        self.technical(d)
        self.memo(d)
        self.script(d)
