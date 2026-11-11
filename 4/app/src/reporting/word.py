"""Render calculated report DTOs into the actual user-supplied DOCX template."""
from pathlib import Path
from zipfile import ZipFile
import re
from docx import Document
from docx.shared import Pt,Cm,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from ..io_utils import now,write_json
from ..models import ReportTextDTO,ReportHeadingDTO,ReportFormulaDTO
from ..services.template_report import TemplateReportService
from .template import ReportTemplateLoader,TemplateReportValidationService

REPORT_NAME='Итоговый_отчет_ФИП_Практическая_4.docx'
BLUE='1F4E78'

class WordReportWriter:
    def write(self,path,sections,chart_directory,manifest,inputs=None,*,template_path=None,report_data=None):
        doc,titles,placeholders,template=ReportTemplateLoader().load(template_path)
        self.doc=doc; self.table_number=0; self.figure_number=0; self.block_ids=[]
        self.source_ids={s.section_id for s in sections}
        self.chart_directory=Path(chart_directory)
        self.configure_styles()
        self.content_width=doc.sections[0].page_width-doc.sections[0].left_margin-doc.sections[0].right_margin
        chapters=TemplateReportService().build(titles,sections,inputs,manifest,report_data)
        for chapter in chapters:
            doc.add_heading(chapter.title,1)
            subsection=0
            for block in chapter.blocks:
                if isinstance(block,ReportTextDTO): self.paragraph(block.text,bullet=block.bullet)
                elif isinstance(block,ReportHeadingDTO):
                    doc.add_heading(block.text,2)
                    numbering=re.match(r'^\d+\.(\d+)\.',block.text)
                    if numbering: subsection=int(numbering.group(1))
                elif isinstance(block,ReportFormulaDTO):
                    label=self.paragraph(block.formula_id,bold=True)
                    label.paragraph_format.keep_with_next=True
                    p=doc.add_paragraph(style='FIP Formula'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.keep_with_next=True
                    r=p.add_run(block.equation); r.font.name='Cambria Math'; r.font.size=Pt(12)
                    self.paragraph('где '+block.explanation)
                else:
                    title=None
                    if not block.section_id.startswith('template_'):
                        subsection+=1
                        prefix=chapter.title.split('.')[0]
                        title=f'{prefix}.{subsection}. {block.title}' if prefix.isdigit() else block.title
                    self.render_section(block,title)
        doc.add_heading('Приложение Б. Полные исходные параметры и воспроизведение',1)
        if inputs is not None:
            rows=[(r['parameter_id'],r['jurisdiction']+' / '+r['period_or_scenario'],float(r['value']),r['unit'],r['source_page']) for r in inputs.provenance]
            self.table(('Параметр','Страна / период','Значение','Единица','PDF, стр.'),rows,'Полные входные параметры')
            self.paragraph('Все параметры имеют исходный текст, страницу и единицу в data/*.csv. Полные годовые результаты без округления — tables/annual_cashflows.csv; сценарии — all_scenario_cashflows.csv; независимая формульная книга — Ground_Truth.xlsx.')
        self.paragraph('Единый запуск: python 4/app/main.py. Подготовленное окружение: 4/app/.venv/Scripts/python.exe 4/app/main.py. Зависимости: requirements.txt. Контрольная копия шаблона: data/report_template.docx; другой источник задается --template.')
        self.paragraph(f'Run ID: {manifest.get("run_id","test")}; дата: {now()[:10]}; статус: {manifest.get("status","NOT_VERIFIED")}. SHA256 шаблона: {template["sha256"]}.')
        self.paragraph('Коды возврата: 0 — SUCCESS/COMPLETED_WITH_LIMITATIONS; 2 — NOT_VERIFIED; 1 — FAILED. Без реального пересчета Excel или подтвержденного просмотра PNG проверка не объявляется полной. Подробности исполнения и хеши артефактов — run_manifest.json/package_manifest.json; история — logs/events.jsonl.')
        footer=doc.sections[0].footer.paragraphs[0]
        footer.paragraph_format.first_line_indent=0
        instructions=[e.text or '' for e in footer._p.iter(qn('w:instrText'))]
        instructions += [e.get(qn('w:instr'),'') for e in footer._p.iter(qn('w:fldSimple'))]
        if not footer.text and not any('PAGE' in instruction for instruction in instructions):
            footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
            field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); footer._p.append(field)
        audit=TemplateReportValidationService().validate(doc,titles,placeholders,self.figure_number,
            [s.section_id for s in sections],self.block_ids)
        doc.save(path)
        with ZipFile(path) as z:
            media=[n for n in z.namelist() if n.startswith('word/media/')]
            if len(media)!=self.figure_number: raise ValueError('DOCX embedded figure count mismatch')
            if z.testzip(): raise ValueError('DOCX CRC failed')
        Document(path)
        result=dict(sections=len(sections),chapters=12,tables=len(doc.tables),figures=self.figure_number,status='PASS',
            order='table→graph→analysis',template=template,template_validation=audit,block_ids=self.block_ids,
            chapter_titles=list(titles))
        write_json(Path(path).with_name('report_structure.json'),result)
        return result

    def configure_styles(self):
        styles=self.doc.styles; normal=styles['Normal']
        normal.font.name='Times New Roman'; normal.font.size=Pt(12)
        pf=normal.paragraph_format; pf.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; pf.line_spacing=1.15
        pf.first_line_indent=Cm(1.25); pf.space_after=Pt(6)
        for name,size in [('Heading 1',15),('Heading 2',13)]:
            s=styles[name]; s.font.name='Times New Roman'; s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor.from_string(BLUE)
            s.paragraph_format.keep_with_next=True; s.paragraph_format.first_line_indent=0
            s.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
        for name in ('FIP Formula','FIP Caption'):
            if name not in styles: styles.add_style(name,1)
            s=styles[name]; s.base_style=normal; s.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
            s.paragraph_format.first_line_indent=0
            s.font.name='Cambria Math' if name=='FIP Formula' else 'Times New Roman'
            s.font.size=Pt(12 if name=='FIP Formula' else 10.5)
        # Word gives theme-font attributes precedence over literal names. The
        # original heading styles contain both, so remove theme overrides.
        for name in ('Normal','Heading 1','Heading 2','List Bullet','Footer','Header','FIP Formula','FIP Caption'):
            style=styles[name]; font='Cambria Math' if name=='FIP Formula' else 'Times New Roman'
            style.font.name=font
            fonts=style.element.get_or_add_rPr().find(qn('w:rFonts'))
            for attribute in list(fonts.attrib):
                if 'theme' in attribute.lower(): del fonts.attrib[attribute]
            for script in ('ascii','hAnsi','eastAsia','cs'): fonts.set(qn('w:'+script),font)

    def paragraph(self,text,*,bullet=False,bold=False):
        p=self.doc.add_paragraph(style='List Bullet' if bullet else 'Normal')
        if bullet:
            p.paragraph_format.first_line_indent=0
            p.paragraph_format.line_spacing=1.15
        p.add_run(text).bold=bold
        return p

    @staticmethod
    def format_value(value):
        if value is None: return '—'
        if isinstance(value,float):
            if abs(value)>=1e12: return f'{value:.6e}'
            return f'{value:,.4f}'.replace(',',' ').rstrip('0').rstrip('.')
        return str(value)

    def table(self,columns,rows,title):
        self.table_number+=1
        caption=self.doc.add_paragraph(style='FIP Caption'); caption.paragraph_format.keep_with_next=True
        caption.add_run(f'Таблица {self.table_number} — {title}')
        table=self.doc.add_table(rows=1,cols=len(columns)); table.style='Table Grid'
        table.autofit=False
        for column in table.columns: column.width=int(self.content_width/len(columns))
        for cell,value in zip(table.rows[0].cells,columns):
            cell.text=str(value)
            shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),BLUE); cell._tc.get_or_add_tcPr().append(shd)
        header=OxmlElement('w:tblHeader'); table.rows[0]._tr.get_or_add_trPr().append(header)
        for values in rows:
            for cell,value in zip(table.add_row().cells,values): cell.text=self.format_value(value)
        for index,row in enumerate(table.rows):
            no_split=OxmlElement('w:cantSplit'); row._tr.get_or_add_trPr().append(no_split)
            for cell in row.cells:
                cell.width=int(self.content_width/len(columns))
                for p in cell.paragraphs:
                    p.paragraph_format.first_line_indent=0; p.paragraph_format.space_after=Pt(2)
                    p.paragraph_format.line_spacing=1.0
                    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if index==0 else WD_ALIGN_PARAGRAPH.LEFT
                    for run in p.runs:
                        run.font.name='Times New Roman'; run.font.size=Pt(9 if len(columns)>5 else 10.5)
                        if index==0: run.bold=True; run.font.color.rgb=RGBColor(255,255,255)
        return table

    def render_section(self,block,title):
        if title: self.doc.add_heading(title,2)
        if block.section_id in self.source_ids: self.block_ids.append(block.section_id)
        self.table(block.columns,block.rows,block.title)
        if block.chart_id:
            picture=self.chart_directory/(block.chart_id+'.png')
            if not picture.is_file(): raise FileNotFoundError(picture)
            self.figure_number+=1
            p=self.paragraph(f'На рисунке {self.figure_number} показаны результаты таблицы {self.table_number}: {block.title.lower()}.')
            p.paragraph_format.keep_with_next=True
            p=self.doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent=0; p.paragraph_format.keep_with_next=True
            p.add_run().add_picture(str(picture),width=int(self.content_width))
            p=self.doc.add_paragraph(style='FIP Caption'); p.paragraph_format.keep_with_next=True
            p.add_run(f'Рисунок {self.figure_number} — {block.title}. Источник: {block.table_id}.csv; код {block.chart_id}.')
        p=self.doc.add_paragraph(); p.add_run('Анализ и выводы. ').bold=True; p.add_run(block.analysis)

    def markdown(self,path,sections,summary):
        lines=['# Итоги практической работы 4',f'\nСтатус: {summary["status"]}\n']
        for s in sections:
            lines.extend([f'## {s.section_id}. {s.title}','', '| '+' | '.join(s.columns)+' |','| '+' | '.join('---' for _ in s.columns)+' |'])
            lines.extend('| '+' | '.join(str(v) for v in row)+' |' for row in s.rows)
            if s.chart_id: lines.extend(['',f'![{s.title}](charts/{s.chart_id}.png)'])
            lines.extend(['',s.analysis,''])
        Path(path).write_text('\n'.join(lines),encoding='utf-8')
