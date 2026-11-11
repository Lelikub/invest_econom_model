"""Read the actual user template, retaining cover XML, styles and page setup."""
from copy import deepcopy
from pathlib import Path
import re
from docx import Document
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from ..io_utils import sha256,now

TEMPLATE_NAME='Шаблон_отчета_ЭА_краткий_v2 (3).docx'

class ReportTemplateLoader:
    @staticmethod
    def default_path() -> Path:
        app=Path(__file__).resolve().parents[2]
        copy=app/'data/report_template.docx'
        return copy if copy.is_file() else app.parents[1]/'lectuion'/TEMPLATE_NAME

    def load(self,path: Path | None = None):
        path=Path(path) if path is not None else self.default_path()
        if not path.is_file(): raise FileNotFoundError(f'Required report template: {path}')
        try: doc=Document(path)
        except Exception as e: raise ValueError(f'Unusable DOCX report template: {path}') from e
        headings=[p for p in doc.paragraphs if p.style.name=='Heading 1']
        if len(headings)!=13 or [int(re.match(r'^(\d+)\.',p.text).group(1)) if re.match(r'^(\d+)\.',p.text) else None for p in headings]!=list(range(1,14)):
            raise ValueError('Report template must contain the twelve content chapters and chapter13 style instructions')
        if 'Правила сохранения стиля' not in headings[-1].text or len(doc.tables)<10:
            raise ValueError('Unsupported report template structure')
        titles=tuple(p.text for p in headings[:12])
        all_text=[p.text for p in doc.paragraphs]+[c.text for t in doc.tables for row in t.rows for c in row.cells]
        placeholders=set(re.findall(r'\[[^\[\]\n]+\]','\n'.join(all_text)))
        first=headings[0]._p; body=doc.element.body; removing=False
        for element in list(body):
            if element is first: removing=True
            if removing and element.tag!=qn('w:sectPr'): body.remove(element)
        replacements={
            '[N]':'4',
            '[НАЗВАНИЕ ПРАКТИЧЕСКОЙ РАБОТЫ]':'Учет странового и геополитического риска инвестиционного проекта',
            '[ОБЪЕКТ ИССЛЕДОВАНИЯ]':'Greenfield-завод PFSA-мембран и мембранно-электродных блоков PEM-электролизеров: Германия, Сербия, Вьетнам',
            '[ГОРОД]':'Город: ____________________','[ГОД]':now()[:4],
            '«Экономический анализ наукоёмких производств»':'«Финансово-инвестиционное проектирование (ФИП)»'}
        for paragraph in doc.paragraphs:
            text=paragraph.text
            for old,new in replacements.items(): text=text.replace(old,new)
            if text!=paragraph.text:
                if paragraph.runs:
                    paragraph.runs[0].text=text
                    for run in paragraph.runs[1:]: run.text=''
                else: paragraph.add_run(text)
            # The normal body indent must not move centered cover paragraphs.
            paragraph.paragraph_format.first_line_indent=0
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs: paragraph.paragraph_format.first_line_indent=0
        # This supplied template contains two orphan image relationships. Do not
        # carry unused sample media into the final report or count it as a chart.
        referenced={value for element in doc.element.iter() for name,value in element.attrib.items()
            if name.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}')}
        for rid,relationship in list(doc.part.rels.items()):
            if relationship.reltype==RT.IMAGE and rid not in referenced: doc.part.drop_rel(rid)
        return doc,titles,placeholders,dict(path=str(path.resolve()),sha256=sha256(path),name=path.name)

class TemplateReportValidationService:
    def validate(self,doc,chapter_titles,placeholders,chart_count,expected_blocks,actual_blocks):
        headings=[p.text for p in doc.paragraphs if p.style.name=='Heading 1']
        if headings[:12]!=list(chapter_titles): raise ValueError('Template chapter order mismatch')
        if any('Правила сохранения стиля при заполнении шаблона' in p.text for p in doc.paragraphs): raise ValueError('Template instructions leaked into final report')
        text='\n'.join([p.text for p in doc.paragraphs]+[c.text for t in doc.tables for row in t.rows for c in row.cells])
        remaining=[p for p in placeholders if p in text]
        if remaining: raise ValueError('Unfilled template placeholders: '+str(remaining))
        if sorted(expected_blocks)!=sorted(actual_blocks) or len(actual_blocks)!=len(set(actual_blocks)):
            raise ValueError('Calculation sections lost or duplicated in template layout')
        if len(doc.inline_shapes)!=chart_count: raise ValueError('Template embedded chart count mismatch')
        normal=doc.styles['Normal']
        if normal.font.name!='Times New Roman' or normal.font.size.pt!=12: raise ValueError('Template normal font mismatch')
        for name,size in [('Heading 1',15),('Heading 2',13)]:
            style=doc.styles[name]
            if style.font.name!='Times New Roman' or style.font.size.pt!=size or str(style.font.color.rgb)!='1F4E78':
                raise ValueError('Template heading style mismatch')
            fonts=style.element.rPr.find(qn('w:rFonts'))
            if any('theme' in key.lower() for key in fonts.attrib): raise ValueError('Word theme overrides heading font')
        instructions=[e.text or '' for e in doc.sections[0].footer._element.iter(qn('w:instrText'))]
        instructions += [e.get(qn('w:instr'),'') for e in doc.sections[0].footer._element.iter(qn('w:fldSimple'))]
        if sum('PAGE' in text for text in instructions)>1: raise ValueError('Duplicate PAGE fields in footer')
        for table in doc.tables[1:]:
            if table.style.name!='Table Grid': raise ValueError('Template table style mismatch')
        return dict(status='PASS',chapters=12,placeholders_remaining=0,calculation_blocks=len(actual_blocks),
            figures=chart_count,cover_from_template=True,style_instructions_removed=True)
