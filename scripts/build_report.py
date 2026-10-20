"""Сборка Word из docs/report.md: pip install python-docx pillow; python scripts/build_report.py."""
import json
import re
from pathlib import Path
from PIL import Image
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
text=(DOCS/'report-template.md').read_text()
bench=json.loads((DOCS/'benchmark.json').read_text())
text=text.replace('{{BENCHMARK}}',f"Каталог содержал {bench['records']} доступных объектов. Среднее время ответа — {bench['mean_ms']} мс, p95 — {bench['p95_ms']} мс, максимум — {bench['max_ms']} мс. Среда: {bench['environment']}. Параллелизм — один запрос. Значения приведены для HTTP-чтения каталога, а не для вычисления хеша пароля.")
result=(DOCS/'test-results.txt').read_text()
summary=result[result.index('Name '):].strip()
text=text.replace('{{RESULTS}}','```text\n'+summary+'\n```')
pages=text.split('<!-- page -->')
# После первого рендера можно сохранить фактические номера разделов в JSON.
page_map_path=DOCS/'report-pages.json'
page_map=json.loads(page_map_path.read_text()) if page_map_path.exists() else {}
contents=[]
for i,page in enumerate(pages):
    prose=re.sub(r'```.*?```','',page,flags=re.S)
    for level,title in re.findall(r'^(#{1,2}) (.+)$',prose,re.M):
        if i>2:
            contents.append(('    ' if level=='##' else '')+title+'\t'+str(page_map.get(title,i+1)))
text=text.replace('{{CONTENTS}}','\n\n'.join(contents))
pages=text.split('<!-- page -->')
(DOCS/'report.md').write_text(text)
doc=Document(); section=doc.sections[0]
section.page_width=Cm(21);section.page_height=Cm(29.7)
section.top_margin=Cm(2);section.bottom_margin=Cm(2);section.left_margin=Cm(3);section.right_margin=Cm(1.5)
section.header_distance=Cm(1);section.footer_distance=Cm(1.1);section.different_first_page_header_footer=True
normal=doc.styles['Normal'];normal.font.name='Times New Roman';normal.font.size=Pt(14);normal.font.color.rgb=RGBColor(0,0,0)
normal.paragraph_format.line_spacing=1.5;normal.paragraph_format.space_after=Pt(0);normal.paragraph_format.first_line_indent=Cm(1.25)
for name,size in [('Title',18),('Heading 1',16),('Heading 2',14)]:
    s=doc.styles[name];s.font.name='Times New Roman';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0)
    s.font.bold=True;s.paragraph_format.first_line_indent=Cm(0);s.paragraph_format.space_before=Pt(0);s.paragraph_format.space_after=Pt(10);s.paragraph_format.keep_with_next=True
    s.paragraph_format.line_spacing=1.2
for style in doc.styles:
    for border in list(style.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
code=doc.styles.add_style('Source Code',1);code.font.name='Courier New';code.font.size=Pt(9)
code.paragraph_format.first_line_indent=Cm(0);code.paragraph_format.line_spacing=1.05;code.paragraph_format.space_after=Pt(0)
caption=doc.styles['Caption'];caption.font.name='Times New Roman';caption.font.size=Pt(12);caption.font.color.rgb=RGBColor(0,0,0)
caption.paragraph_format.first_line_indent=Cm(0);caption.paragraph_format.line_spacing=1.1;caption.paragraph_format.space_after=Pt(9)
f=section.footer.paragraphs[0];f.alignment=WD_ALIGN_PARAGRAPH.CENTER;f.paragraph_format.first_line_indent=Cm(0)
r=f.add_run();field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');r._r.addnext(field)
doc.core_properties.author='Волков Лев Геннадьевич';doc.core_properties.title='Разработка веб-сервиса аренды недвижимости'
doc.core_properties.subject='Курсовая работа';doc.core_properties.keywords='FastAPI SQLite аренда недвижимости'

def para(value,style=None):
    p=doc.add_paragraph(value,style);p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    return p

table_number=0
def table(lines):
    global table_number
    table_number += 1
    p=doc.add_paragraph(f'Таблица {table_number}','Caption');p.paragraph_format.keep_with_next=True
    values=[[cell.strip() for cell in line.strip().strip('|').split('|')] for line in lines]
    values=[v for v in values if not all(re.fullmatch(r':?-+:?',x) for x in v)]
    t=doc.add_table(rows=0,cols=len(values[0]));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    widths={2:[5,11.5],3:[4.0,3.3,9.2],4:[4.6,6.1,2.9,2.9]}.get(len(values[0]),[16.5/len(values[0])]*len(values[0]))
    # Четырёхколоночные матрицы прав требуют равной ширины коротких колонок.
    if len(values[0])==4 and values[0][0]=='Операция':widths=[6.0,2.5,4,4]
    if len(values[0])==4 and values[0][0]=='Исходный статус':widths=[4.2,4,4,4.3]
    for j,w in enumerate(widths):t.columns[j].width=Cm(w)
    for row_i,values_row in enumerate(values):
        row=t.add_row();trpr=row._tr.get_or_add_trPr();no_split=OxmlElement('w:cantSplit');trpr.append(no_split)
        if row_i==0:
            repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
        for j,value in enumerate(values_row):
            cell=row.cells[j];cell.width=Cm(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr=cell._tc.get_or_add_tcPr();borders=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
            tcpr.append(borders)
            margins=OxmlElement('w:tcMar')
            for side in ['top','left','bottom','right']:
                el=OxmlElement('w:'+side);el.set(qn('w:w'),'85');el.set(qn('w:type'),'dxa');margins.append(el)
            tcpr.append(margins)
            if row_i==0:
                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E8ECE8');tcpr.append(sh)
            p=cell.paragraphs[0];p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1.05;p.paragraph_format.space_after=Pt(1)
            if j>0 and len(value)<15:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            run=p.add_run(value);run.font.name='Times New Roman';run.font.size=Pt(11);run.bold=row_i==0
    doc.add_paragraph().paragraph_format.space_after=Pt(0)

for page_i,page in enumerate(pages):
    starts_chapter = page.strip().startswith('# ')
    new_chapter = page_i > 0 and starts_chapter
    if page_i==0:
        for i,line in enumerate(x.strip() for x in page.strip().splitlines() if x.strip()):
            if line.startswith('# '):
                p=doc.add_paragraph(line[2:],'Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(35);p.paragraph_format.space_after=Pt(24)
            else:
                p=doc.add_paragraph(line);p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_after=Pt(16);p.paragraph_format.line_spacing=1.5
                if i in (1,6,11):p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        continue
    lines=page.strip().splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            i+=1
            while i<len(lines) and not lines[i].startswith('```'):
                p=doc.add_paragraph(lines[i],'Source Code');i+=1
            doc.add_paragraph().paragraph_format.space_after=Pt(0)
        elif line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i]);i+=1
            table(rows);continue
        elif line.startswith('# '):
            p=doc.add_paragraph(line[2:],'Heading 1')
            if new_chapter:p.paragraph_format.page_break_before=True
        elif line.startswith('## '):
            p=doc.add_paragraph(line[3:],'Heading 2');p.paragraph_format.space_before=Pt(12)
            if line.startswith('## 4 ') and not line.startswith('## 4 1 '):p.paragraph_format.page_break_before=True
        elif line.startswith('!['):
            m=re.match(r'!\[(.*?)\]\((.*?)\)',line);path=DOCS/m.group(2)
            with Image.open(path) as im:w,h=im.size
            max_h=11.5
            if 'prototypes' in str(path):max_h=8.5
            if '02-registration' in str(path):max_h=9.5
            scale=min(16.4/w,max_h/h)
            p=doc.add_paragraph();p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.keep_with_next=True;p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            pic=p.add_run().add_picture(str(path),width=Cm(w*scale),height=Cm(h*scale));pic._inline.docPr.set('descr',m.group(1))
            p=doc.add_paragraph(m.group(1),'Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        elif page_i==2:
            p=doc.add_paragraph(line);p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1.05;p.paragraph_format.space_after=Pt(3)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(16),WD_ALIGN_PARAGRAPH.RIGHT)
            for run in p.runs:run.font.size=Pt(11)
        else:para(line)
        i+=1
out=DOCS/'coursework-report.docx';doc.save(out);print(out)
