from copy import deepcopy
from pathlib import Path
import hashlib
import re
import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from conftest import APP
from src.models import ReportSectionDTO

EXTERNAL_TEMPLATE=APP.parents[1]/'lectuion/Шаблон_отчета_ЭА_краткий_v2 (3).docx'
TEMPLATE=EXTERNAL_TEMPLATE if EXTERNAL_TEMPLATE.is_file() else APP/'data/report_template.docx'

def write_report(tmp_path,template=TEMPLATE):
    from src.reporting.word import WordReportWriter
    section=ReportSectionDTO('T01','Проверяемый результат','test_table',None,
        ('Страна','Parent NPV, USD'),(('DEU',-10.),),'Проверенный вывод: NPV отрицателен.')
    path=tmp_path/'report.docx'
    result=WordReportWriter().write(path,[section],tmp_path,{'status':'NOT_VERIFIED','run_id':'template-test'},template_path=template)
    return Document(path),result,path

def test_real_template_cover_and_chapter_order(tmp_path):
    doc,result,path=write_report(tmp_path)
    headings=[p.text for p in doc.paragraphs if p.style.name=='Heading 1']
    source=[p.text for p in Document(TEMPLATE).paragraphs if p.style.name=='Heading 1'][:12]
    assert headings[:12]==source
    text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    assert text.startswith('МИНИСТЕРСТВО НАУКИ И ВЫСШЕГО ОБРАЗОВАНИЯ')
    assert 'ОТЧЁТ ПО ПРАКТИЧЕСКОЙ РАБОТЕ № 4' in text
    assert 'Правила сохранения стиля при заполнении шаблона' not in text
    assert 'Проверенный вывод: NPV отрицателен.' in text
    assert 'Выполнили:' in text and 'Проверил:' in text
    for marker in ['[N]','[ГОРОД]','[ГОД]','[ОБЪЕКТ ИССЛЕДОВАНИЯ]','[значение]','[НАЗВАНИЕ ПРАКТИЧЕСКОЙ РАБОТЫ]']:
        assert marker not in text
    assert result['template']['sha256']==hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    assert result['template_validation']['status']=='PASS'

def test_template_page_setup_and_styles(tmp_path):
    doc,result,path=write_report(tmp_path); original=Document(TEMPLATE)
    for attr in ['page_width','page_height','left_margin','right_margin','top_margin','bottom_margin']:
        assert getattr(doc.sections[0],attr)==getattr(original.sections[0],attr)
    normal=doc.styles['Normal']
    assert normal.font.name=='Times New Roman' and normal.font.size.pt==12
    assert normal.paragraph_format.alignment==WD_ALIGN_PARAGRAPH.JUSTIFY
    assert normal.paragraph_format.line_spacing==pytest.approx(1.15)
    assert normal.paragraph_format.first_line_indent.cm==pytest.approx(1.25,abs=.01)
    for name,size in [('Heading 1',15),('Heading 2',13)]:
        style=doc.styles[name]
        assert style.font.size.pt==size
        assert str(style.font.color.rgb)=='1F4E78'
    tables=doc.tables[1:]
    assert tables and all(t.style.name=='Table Grid' for t in tables)
    for table in tables:
        for cell in table.rows[0].cells:
            assert cell._tc.tcPr.find(qn('w:shd')).get(qn('w:fill'))=='1F4E78'
            assert all(run.bold and str(run.font.color.rgb)=='FFFFFF' for p in cell.paragraphs for run in p.runs)
    formula=[p for p in doc.paragraphs if p.style.name=='FIP Formula']
    assert formula and all(p.alignment==WD_ALIGN_PARAGRAPH.CENTER for p in formula)
    assert all(r.font.name=='Cambria Math' and r.font.size.pt==12 for p in formula for r in p.runs)

def test_word_theme_cannot_override_heading_fonts_or_duplicate_page_numbers(tmp_path):
    doc,result,path=write_report(tmp_path)
    for name in ('Normal','Heading 1','Heading 2','FIP Formula','FIP Caption'):
        fonts=doc.styles[name].element.rPr.find(qn('w:rFonts'))
        assert fonts is not None
        assert not any('theme' in key.lower() for key in fonts.attrib),name
    footer=doc.sections[0].footer._element
    instructions=[e.text or '' for e in footer.iter(qn('w:instrText'))]
    instructions += [e.get(qn('w:instr'),'') for e in footer.iter(qn('w:fldSimple'))]
    assert sum('PAGE' in text for text in instructions)==1

def test_provided_template_is_used_and_left_unchanged(tmp_path):
    custom=tmp_path/'custom.docx'; d=Document(TEMPLATE)
    d.sections[0].header.paragraphs[0].text='Проверка использования выбранного шаблона'
    d.save(custom); before=hashlib.sha256(custom.read_bytes()).hexdigest()
    doc,result,path=write_report(tmp_path,custom)
    assert doc.sections[0].header.paragraphs[0].text=='Проверка использования выбранного шаблона'
    assert hashlib.sha256(custom.read_bytes()).hexdigest()==before

@pytest.mark.parametrize('fault',['missing','corrupt','wrong_structure'])
def test_unusable_template_never_silently_falls_back(tmp_path,fault):
    source=tmp_path/'template.docx'
    if fault=='corrupt': source.write_bytes(b'not a docx')
    if fault=='wrong_structure': Document().save(source)
    with pytest.raises((ValueError,FileNotFoundError)):
        write_report(tmp_path,source)

def test_template_layout_keeps_all_blocks_and_local_chart_order(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from src.reporting.word import WordReportWriter
    fig,ax=plt.subplots(); ax.plot([0,1],[0,1]); fig.savefig(tmp_path/'chart.png'); plt.close(fig)
    blocks=[ReportSectionDTO('03','Риски','risk_table','chart',('Страна','Ставка'),(('DEU',.091),),'Проверенный анализ рисков.')]
    path=tmp_path/'report.docx'
    result=WordReportWriter().write(path,blocks,tmp_path,{'status':'NOT_VERIFIED'},template_path=TEMPLATE)
    doc=Document(path)
    children=list(doc.element.body)
    chart_index=next(i for i,e in enumerate(children) if e.findall('.//'+qn('w:drawing')))
    table_index=max(i for i,e in enumerate(children[:chart_index]) if e.tag==qn('w:tbl'))
    analysis_index=next(i for i,e in enumerate(children) if 'Проверенный анализ рисков.' in ''.join(e.itertext()))
    assert table_index<chart_index<analysis_index
    assert len(doc.inline_shapes)==1
    assert result['block_ids']==['03']

def test_layout_contains_template_control_tables(inputs,tmp_path):
    from src.services.scenarios import ScenarioService
    from src.services.tables import TableService
    from src.services.report_sections import ReportService
    from src.reporting.word import WordReportWriter
    from src.reporting.charts import ChartService
    scenarios=ScenarioService().run(inputs)
    tables=TableService().write(inputs,scenarios,tmp_path/'tables')
    ChartService().write(tmp_path/'tables',tmp_path/'charts')
    tests=[dict(test_id='check',status='PASS',seconds=0.,details='')]
    rec=[dict(metric_id='npv',country='DEU',python_value=-10.,excel_value=-10.,absolute_diff=0.,unit='USD',status='PASS')]
    issue=dict(id='REAL',kind='CODE_ERROR',observed='Наблюдаемая ошибка',decision='Исправлено',retest='PASS',status='PASS',stage='review')
    manifest=dict(status='COMPLETED_WITH_LIMITATIONS',excel=dict(status='PASS'),run_id='test')
    sections=ReportService().sections(inputs,scenarios,tables,rec,tests,manifest,[issue])
    p=tmp_path/'report.docx'
    WordReportWriter().write(p,sections,tmp_path/'charts',manifest,inputs,template_path=TEMPLATE,
        report_data=dict(tests=tests,reconciliation=rec,issues=[issue],scenario_inputs=tables['scenario_inputs']))
    doc=Document(p); headers=[[c.text for c in table.rows[0].cells] for table in doc.tables[1:]]
    expected=[['Параметр','Техническое имя / источник','Базовый сценарий','Сценарий 2','Единица'],
        ['Этап','Поток','Назначение'],['Метрика','Значение','Единица измерения','Статус'],['Поле','Содержание'],
        ['Тест / сценарий','Проверяемое свойство','Результат','Статус'],
        ['Метрика','Базовый','Сценарный','Абс. изменение','Отн. изменение','Интерпретация'],
        ['Код','Допущение','Обоснование','Влияние'],['Проблема','Параметр','Критичность','Влияние','Действие']]
    for columns in expected: assert columns in headers
    assert len(doc.inline_shapes)==13
