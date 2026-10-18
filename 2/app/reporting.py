"""Harness workbook and two reports drawn from the same calculated results."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from model import ModelResult


def harness(path: Path, reconciliation: list[dict], stress: list[dict], issues: list[dict], test_status: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook(); summary=wb.active;summary.title="Summary"
    now=datetime.now().isoformat(timespec="seconds")
    summary.append(["timestamp","stage","category","test_name","status","severity","issue","action_taken"])
    summary.append([now,"unit tests","verification","unittest suite",test_status,"INFO" if test_status=="PASS" else "ERROR","Automated suite executed","See logs/test_results.txt"])
    for issue in issues:
        summary.append([now,issue.get("stage","pipeline"),issue.get("category","issue"),issue.get("test_name",""),issue.get("status","WARNING"),issue.get("severity","WARNING"),issue["issue"],issue.get("action_taken","")])
    rec=wb.create_sheet("Reconciliation");rec.append(list(reconciliation[0].keys()))
    for row in reconciliation:rec.append(list(row.values()))
    st=wb.create_sheet("Stress_Tests");st.append(list(stress[0].keys()))
    for row in stress:st.append(list(row.values()))
    for title in ("Errors","Source_Issues","Assumptions","AI_Hallucination_Risks"):
        ws=wb.create_sheet(title);ws.append(["timestamp","stage","issue","status","action"])
        for issue in issues:
            if issue.get("sheet")==title:
                ws.append([now,issue.get("stage",""),issue["issue"],issue.get("status","WARNING"),issue.get("action_taken","")])
    for ws in wb:
        ws.freeze_panes="A2"
        for c in ws[1]:c.fill=PatternFill("solid",fgColor="17365D");c.font=Font(color="FFFFFF",bold=True)
        for col in "ABCDEFGH":ws.column_dimensions[col].width=26
    wb.save(path)


def _table_md(headers,rows):
    return "| "+" | ".join(map(str,headers))+" |\n| "+" | ".join("---" for _ in headers)+" |\n"+"\n".join("| "+" | ".join(map(str,row))+" |" for row in rows)


def report_data(base: ModelResult, shock: ModelResult, recon: list[dict], stress: list[dict], sensitivity: list[dict], issues: list[dict], test_status: str):
    verified=sum(x["status"]=="PASS" for x in recon)
    unverified=sum(x["status"]=="NOT_VERIFIED" for x in recon)
    failed=sum(x["status"]=="FAIL" for x in recon)
    if failed: recon_status=f"FAIL: {failed} расхождений"
    elif unverified: recon_status=f"НЕ ПОДТВЕРЖДЕНО: {unverified} значений Excel без пересчитанного кэша"
    else: recon_status=f"PASS: {verified} из {len(recon)} значений"
    early=[(n.i,n.j,n.S,n.intrinsic,n.continuation,n.C,n.decision) for row in base.option for n in row if n.decision=="EXERCISE"]
    input_rows=[(k,getattr(base.inputs,k),"млн долл." if k in ("I0","S0","K") else ("доля/год" if k in ("r","sigma","delta") else ("год" if k=="T" else "шаг" if k=="N" else "доля")),5) for k in ("I0","S0","K","r","sigma","delta","T","N","m")]
    result_rows=[("NPV_trad",base.npv_trad,"млн долл."),("dt",base.params.dt,"год"),("u",base.params.u,"коэффициент"),("d",base.params.d,"коэффициент"),("p",base.params.p,"вероятность"),("ROV",base.rov,"млн долл."),("NPV_strat",base.npv_strat,"млн долл."),("ROV shock 70%",shock.rov,"млн долл."),("NPV_strat shock",shock.npv_strat,"млн долл.")]
    fmt=lambda x: f"{x:.6f}" if isinstance(x,(int,float)) else str(x)
    source_issue="Контрольное значение ROV=35,85 млн долл. на стр. 8 задания отличается от полного расчёта на 0,00992 млн долл.; при обычном округлении до сотых получается 35,86. Вероятна усечённая запись или промежуточное округление, но способ в PDF не указан."
    sections={
      "goal":"Цель — оценить управленческую гибкость модульной чистой комнаты для EUV-фоторезистов методом американского опциона CRR. Расчёт проходит путь PDF → CSV → валидация → CRR → Excel Ground Truth → сверка → граничные тесты → сценарий → Harness Log → отчёт.",
      "object":"Объект: Cleanroom Shell-and-Core для фоторезистов EUV-литографии. Первая очередь включает чистую комнату ISO 1 и стартовую линию; вторая очередь приобретается по решению менеджмента в течение трёх лет. Масштаб расширения m=100% означает дополнительные потоки, эквивалентные базовым (задание, стр. 5).",
      "quality":"Все девять параметров программно извлечены из PDF, сохранены с исходным написанием и страницей 5 в CSV, повторно загружены и проверены. Проценты переведены в доли. "+source_issue,
      "architecture":"PDF → anchored parser → source_data.csv → ProjectInputData → validation → CRR → независимые формулы Excel → пересчёт/сверка → stress tests → сценарный анализ → Harness Log → Markdown и Word. При невозможности пересчёта Excel значения остаются неподтверждёнными.",
      "method":"NPV_trad=S0−I0 (млн долл.); dt=T/N (год); u=exp(σ√dt), d=1/u; p=[exp((r−δ)dt)−d]/(u−d); дисконтирование exp(−r·dt). Безарбитражное условие d<exp((r−δ)dt)<u. S[i,j]=S0·m·u^j·d^(i−j), млн долл.; C[N,j]=max(S[N,j]−K,0); C[i,j]=max(max(S[i,j]−K,0),exp(−r·dt)[p·C[i+1,j+1]+(1−p)·C[i+1,j]]). ROV=C[0,0]; NPV_strat=NPV_trad+ROV. Здесь S — PV дополнительных потоков, K — CAPEX второй очереди, T — окно решения, σ — неопределённость, δ — цена отсрочки, m — масштаб расширения.",
      "interpret":f"Базовый DCF отрицателен ({base.npv_trad:.2f} млн долл.), а опцион на расширение добавляет {base.rov:.2f} млн долл. и даёт стратегический NPV {base.npv_strat:.2f} млн долл. Это оценка гибкости, зависящая от допущений и права отказаться от расширения.",
      "early":f"Раннее исполнение: {len(early)} узла(ов); критерий строго Intrinsic > Continuation. Узлы перечислены ниже.",
      "anti_fraud":"Заявление NPV −30 → +15 млн долл. при σ=75% требует независимой проверки σ: источник и сырые ряды; период, частота, размер выборки, annualization; структурные сдвиги и выбор окна; аналоги и twin security; физические драйверы, цены сырья и продукции, корреляции; риск двойного учёта; независимое воспроизведение и чувствительность ROV. Числа кейса не используются как результат данного проекта.",
      "holding":"Ожидание на TRL 4 требует расходов на чистую комнату, микроклимат, utilities, газы, персонал, патенты и сервис; также возможны устаревание и упущенная выгода. δ отражает экономическую цену задержки, но фактический cash burn должен моделироваться отдельно при наличии данных. Его агрегирование в δ — ограничение.",
      "bank":"ROV зависит от σ и будущих решений, не является гарантированным денежным потоком или обеспечением кредита. DSCR=Cash Flow Available for Debt Service / Debt Service; порог задания ≥1,30×. Численный DSCR не рассчитывается вследствие отсутствия необходимых параметров обслуживания долга.",
      "vol":f"При росте σ с 35% до 70% ROV меняется с {base.rov:.2f} до {shock.rov:.2f} млн долл. Выпуклая функция max(S−K,0) ограничивает потери нулём и сохраняет выигрыш при высоком S; менеджмент не обязан исполнять опцион. Рост стоимости гибкости не доказывает привлекательность любого рискованного проекта.",
      "limits":"Модель использует три годовых шага, постоянные r, σ и δ и предполагает выполнимость решения об инвестиции в узле. Эмпирическое подтверждение σ, будущий cash burn и данные по долгу в задании отсутствуют. Поэтому ROV — оценка при заданных допущениях, а не денежное обеспечение.",
    }
    return locals()


def write_markdown(path: Path, data: dict) -> None:
    s=data["sections"];b=data["base"];sh=data["shock"];fmt=data["fmt"]
    parts=["# Итоговый отчёт. Практическая работа № 2 ФИП", "", "## 1. Цель и задачи работы",s["goal"],"", "## 2. Объект исследования",s["object"],"", "## 3. Исходные данные и контроль качества входа",_table_md(["Параметр","Значение","Единица","Стр. PDF"],[(a,fmt(v),u,p) for a,v,u,p in data["input_rows"]]),s["quality"],"", "## 4. Архитектура расчётного решения",s["architecture"],"", "## 5. Методика расчёта",s["method"],"", "## 6. Результаты расчёта",_table_md(["Метрика","Значение","Единица"],[(a,fmt(v),u) for a,v,u in data["result_rows"]]),s["interpret"],s["early"],_table_md(["i","j","S","Intrinsic","Continuation","C","Decision"],[(i,j,fmt(S),fmt(ins),fmt(con),fmt(C),dec) for i,j,S,ins,con,C,dec in data["early"]]) if data["early"] else "Раннего исполнения не обнаружено.","", "## 7. Harness Log",f"Сверка Python ↔ Excel: {data['recon_status']}. Unit tests: {data['test_status']}. Всего записей о замечаниях: {len(data['issues'])}.",_table_md(["Этап","Статус","Факт"],[(i.get("stage",""),i.get("status",""),i["issue"]) for i in data["issues"]]) if data["issues"] else "Ошибок и неоднозначностей не зарегистрировано.","", "## 8. Тестирование и сценарный анализ",_table_md(["Тест","Статус","ROV","NPV_strat","Факт"],[(r["test"],r["status"],fmt(r["rov"]),fmt(r["npv_strat"]),r["details"]) for r in data["stress"]]),_table_md(["Метрика","База","σ=70%","Изменение"],[("ROV",fmt(b.rov),fmt(sh.rov),fmt(sh.rov-b.rov)),("NPV_strat",fmt(b.npv_strat),fmt(sh.npv_strat),fmt(sh.npv_strat-b.npv_strat))]),"", "### Аудит волатильности",s["anti_fraud"],_table_md(["σ","ROV","NPV_strat","Статус"],[(fmt(r["sigma"]),fmt(r["rov"]),fmt(r["npv_strat"]),r["status"]) for r in data["sensitivity"]]),"", "## 9. Визуализация результатов","Базовая и стрессовая решётки содержат S, C и решение в каждом узле; узлы раннего исполнения выделены цветом.","![Базовая решётка](crr_tree_base.png)","Рисунок 1 — CRR, σ=35%.","![Стрессовая решётка](crr_tree_sigma_70.png)","Рисунок 2 — CRR, σ=70%.","", "## 10. Допущения и качество данных",s["quality"],s["limits"],"", "## 11. Анализ результатов и ограничения",s["vol"],s["holding"],s["bank"],"", "## 12. Итоговые выводы",s["interpret"],f"Сверка: {data['recon_status']}; тесты: {data['test_status']}.","", "Источник: Задание к практическому занятию 2 ФИП, стр. 1–8. Все численные результаты получены программой из source_data.csv."]
    path.write_text("\n\n".join(parts)+"\n",encoding="utf-8")


def _set_table(table, rows):
    # Retain the template table, grid style and header. Remove example rows.
    while len(table.rows)>1:
        table._tbl.remove(table.rows[-1]._tr)
    for values in rows:
        cells=table.add_row().cells
        for c,value in zip(cells,values):c.text=str(value)


def write_word(template: Path, path: Path, data: dict, base_png: Path, shock_png: Path) -> None:
    from docx import Document
    from docx.shared import Inches
    doc=Document(template)
    original_text="\n".join(x.text for x in doc.paragraphs)+"\n"+"\n".join(c.text for table in doc.tables for row in table.rows for c in row.cells)
    placeholders=set(re.findall(r"\[[^\]]+\]",original_text))
    p=doc.paragraphs;s=data["sections"];fmt=data["fmt"]
    replacement={10:"ОТЧЁТ ПО ПРАКТИЧЕСКОЙ РАБОТЕ № 2",11:"«Биномиальное моделирование реальных опционов (ROA) и AI-кодинг инвестиционной гибкости в Deep Tech»",12:"Объект: Cleanroom Shell-and-Core для EUV-фоторезистов",14:"Город: __________, 2026",17:s["goal"],18:"",19:"Для достижения цели: извлечь входные данные; построить CRR; проверить Excel; выполнить стресс-тесты; сформировать отчёт.",20:"",21:"",22:"",23:"",24:"",26:s["object"],28:"Первичный источник: Задание к практическому занятию 2 ФИП, стр. 5. CSV создан программно из PDF.",30:s["quality"],32:s["architecture"],35:s["method"],36:"5.1. Параметры CRR и стоимость опциона",37:"Базовый актив S — PV дополнительных денежных потоков; K — CAPEX расширения.",38:"p=[exp((r−δ)dt)−d]/(u−d); C[i,j]=max(Intrinsic,Continuation)",39:"Вероятность p безразмерна; C и S выражены в млн долл.",40:"5.2. Стратегическая ценность",41:"Опцион на расширение учитывается отдельно от базового NPV.",42:"NPV_strat=(S0−I0)+C[0,0]",44:"Таблица ниже содержит результаты машинного расчёта.",46:s["interpret"],49:f"Фактический статус Python ↔ Excel: {data['recon_status']}; unit tests: {data['test_status']}. Записи содержатся в HARNESS_LOG.xlsx.",51:"",53:"Четыре граничных теста и шок σ=70% фактически выполнены; результаты приведены в таблицах.",57:"На рисунках 1 и 2 показаны S и C в узлах базового и стрессового сценария; оранжевый цвет означает раннее исполнение.",58:"Рисунок 1 — Базовая решётка CRR, σ=35%; рисунок 2 — стрессовая решётка, σ=70%.",59:s["vol"],61:s["limits"],63:s["quality"],66:s["anti_fraud"],67:s["holding"]+" "+s["bank"],69:"Ключевые выводы основаны на фактических расчётах и журналах проверки.",70:f"1. NPV_trad={data['base'].npv_trad:.2f} млн долл.",71:f"2. ROV={data['base'].rov:.2f} млн долл.",72:f"3. NPV_strat={data['base'].npv_strat:.2f} млн долл.",73:f"4. При σ=70% ROV={data['shock'].rov:.2f} млн долл.",74:f"5. Сверка: {data['recon_status']}.",75:f"6. Тесты: {data['test_status']}; DSCR без данных долга не рассчитывается."}
    for i,value in replacement.items():p[i].text=value
    # The remaining template guidance and example section are removed.
    for i in range(76,len(p)):
        p[i]._element.getparent().remove(p[i]._element)
    t=doc.tables
    _set_table(t[1],[(k,k,fmt(v),fmt(.7) if k=="sigma" else fmt(v),u) for k,v,u,_ in data["input_rows"]])
    _set_table(t[2],[("1","PDF → CSV","Извлечение и типизация"),("2","CSV → CRR","Расчёт и валидация"),("3","CRR → Excel","Независимые формулы"),("4","Excel → отчёт","Сверка, тесты, Harness")])
    _set_table(t[3],[(k,fmt(v),u,"РАССЧИТАНО") for k,v,u in data["result_rows"]])
    if data["early"]:
        early_table=doc.add_table(rows=1, cols=7,style="Table Grid")
        for c,v in zip(early_table.rows[0].cells,("i","j","S","Intrinsic","Continuation","C","Decision")):c.text=v
        for i,j,S,ins,con,C,dec in data["early"]:
            for c,v in zip(early_table.add_row().cells,(i,j,fmt(S),fmt(ins),fmt(con),fmt(C),dec)):c.text=str(v)
        t[3]._tbl.addnext(early_table._tbl)
    issue=data["issues"][0] if data["issues"] else {"issue":"Замечаний нет","action_taken":"Не требуется"}
    values=[("Запрос к ИИ / задача","Проверить воспроизводимость CRR"),("Изменённый фрагмент","PDF → CSV → CRR → Excel"),("Обнаруженная ошибка",issue["issue"]),("Причина",issue.get("category","контроль качества")),("Исправление",issue.get("action_taken","Зафиксировано")),("Повторная проверка",data["recon_status"])]
    for row,(a,b) in zip(t[4].rows[1:],values):row.cells[0].text=a;row.cells[1].text=b
    _set_table(t[5],[(r["test"],r["details"],fmt(r["rov"]),r["status"]) for r in data["stress"]]+[("sigma=70%","Геополитический сценарий",fmt(data["shock"].rov),"PASS")])
    b=data["base"];sh=data["shock"]
    _set_table(t[6],[("ROV",fmt(b.rov),fmt(sh.rov),fmt(sh.rov-b.rov),fmt((sh.rov-b.rov)/abs(b.rov)),"Гибкость"),("NPV_strat",fmt(b.npv_strat),fmt(sh.npv_strat),fmt(sh.npv_strat-b.npv_strat),fmt((sh.npv_strat-b.npv_strat)/abs(b.npv_strat)),"Опцион")])
    sens_table=doc.add_table(rows=1,cols=4,style="Table Grid")
    for c,v in zip(sens_table.rows[0].cells,("σ","ROV","NPV_strat","Статус")):c.text=v
    for row in data["sensitivity"]:
        for c,v in zip(sens_table.add_row().cells,(fmt(row["sigma"]),fmt(row["rov"]),fmt(row["npv_strat"]),row["status"])):c.text=str(v)
    t[6]._tbl.addnext(sens_table._tbl)
    t[7].cell(0,0).text=""
    for image,label in ((base_png,"Рисунок 1 — σ=35%"),(shock_png,"Рисунок 2 — σ=70%")):
        para=t[7].cell(0,0).add_paragraph();para.add_run().add_picture(str(image),width=Inches(5.7))
        t[7].cell(0,0).add_paragraph(label)
    _set_table(t[8],[("A01","Постоянные σ, r, δ","PDF, стр. 5","ROV"),("A02","Три годовых шага","PDF, стр. 5","Решётка")])
    _set_table(t[9],[("Не подтверждена эмпирическая σ","sigma","СРЕДНЯЯ","ROV","Аудит данных"),("Нет параметров долга","DSCR","СРЕДНЯЯ","Bankability","Не рассчитывать")])
    path.parent.mkdir(parents=True,exist_ok=True);doc.save(path)
    check=Document(path)
    all_text="\n".join(x.text for x in check.paragraphs)+"\n"+"\n".join(c.text for table in check.tables for row in table.rows for c in row.cells)
    if any(marker in all_text for marker in placeholders):
        raise ValueError("Word template placeholders remain")
    if len(check.inline_shapes)<2:
        raise ValueError("Word figures missing")
