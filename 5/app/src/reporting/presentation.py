from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from ..services.analysis import ids
from .documents import m,nf

PPTX="Защита_Инвесткомитет_5_слайдов.pptx"
NAVY="17364D"
WHITE="FFFFFF"
MUTED="496778"
TEAL="126788"
PALE="EAF3F5"


class SlideDeck:
    def __init__(self,folder):
        self.folder=folder
        self.prs=Presentation()
        self.prs.slide_width=Inches(13.3333)
        self.prs.slide_height=Inches(7.5)

    def box(self,slide,text,x,y,w,h,size=19,bold=False,color=NAVY):
        shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
        tf=shape.text_frame
        tf.word_wrap=True
        tf.margin_left=Pt(0); tf.margin_right=Pt(0); tf.margin_top=Pt(0); tf.margin_bottom=Pt(0)
        tf.vertical_anchor=MSO_ANCHOR.TOP
        p=tf.paragraphs[0]
        p.alignment=PP_ALIGN.LEFT
        p.space_after=Pt(0)
        for i,line in enumerate(text.split("\n")):
            if i: p.add_line_break()
            run=p.add_run()
            run.text=line
            run.font.name="Arial"
            run.font.size=Pt(size)
            run.font.bold=bold
            run.font.color.rgb=RGBColor.from_string(color)
        return shape

    @staticmethod
    def panel(slide,x,y,w,h,color):
        shape=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.fill.solid()
        shape.fill.fore_color.rgb=RGBColor.from_string(color)
        shape.line.fill.background()

    def slide(self,title,subtitle,n):
        slide=self.prs.slides.add_slide(self.prs.slide_layouts[6])
        fill=slide.background.fill
        fill.solid()
        fill.fore_color.rgb=RGBColor.from_string(WHITE)
        self.panel(slide,0,0,13.333,0.12,TEAL)
        self.box(slide,title,.56,.45,12.25,.74,31,True)
        self.box(slide,subtitle,.59,1.24,12.1,.47,15,color=MUTED)
        self.panel(slide,.56,7.03,12.2,.014,"D4E5EA")
        self.box(slide,"Инвестиционный комитет  ·  Практическая работа № 5",.58,7.15,11,.22,10,color=MUTED)
        self.box(slide,f"{n} / 5",12.17,7.13,.6,.24,11,True,color=MUTED)
        return slide

    def chart(self,slide,name,x,y,w):
        slide.shapes.add_picture(str(self.folder/"charts"/f"{name}.png"),Inches(x),Inches(y),width=Inches(w))

    def metric(self,slide,x,y,w,value,label):
        self.panel(slide,x,y,w,1.43,PALE)
        self.box(slide,value,x+.22,y+.22,w-.4,.58,29,True,TEAL)
        self.box(slide,label,x+.22,y+.85,w-.4,.44,14,color=MUTED)

    def point(self,slide,heading,body,x,y,w):
        self.box(slide,heading,x,y,w,.39,18,True)
        self.box(slide,body,x,y+.46,w,1.01,15,color=MUTED)

    def run(self,d):
        base,stress,sc=d["base"],d["stress"],d["sc"]
        p=base["milp"]; exact=base["exact"]; green=stress["green"]; fin=stress["finance"]
        s=self.slide("Производство и инвестиционный выбор",
                     "Завод специальной химии и конструкционных полимеров",1)
        self.metric(s,.57,2.02,3.88,f"{m(p.objective,1)} млн руб.","Квартальная прибыль MILP")
        self.metric(s,4.72,2.02,3.88,f"{nf(exact.npv,0)} млн руб.","Базовый максимум NPV")
        self.metric(s,8.87,2.02,3.88,f"{sc.score_floor} баллов","Регуляторный порог MCDA")
        self.point(s,"Операционный план",
                   f"Выпуск {nf(p.x[0])} т Э-1 и {nf(p.x[2])} т К-3 на трёх агрегатах.",.62,4.21,5.55)
        self.point(s,"Выбор инвестиционного портфеля",
                   f"Финансовая цель — {ids(exact)}. При действии порога MCDA — {ids(green)}.",6.72,4.21,5.66)
        self.box(s,"Горизонт инвестиций — 3 года. Производственный план — на квартал.",.62,6.43,12,.31,12,color=MUTED)

        s=self.slide("Сырьё ограничивает выпуск",
                     "Физическая загрузка и локальная оценка дополнительного сырья в Fixed LP",2)
        self.chart(s,"production",.52,2.02,8.7)
        self.point(s,"NMP",f"Теневая цена {nf(base['fixed'].shadow[3],0)} тыс. руб./л.",9.26,2.12,3.34)
        self.point(s,"Наномодификатор",f"{nf(base['fixed'].shadow[4],0)} тыс. руб./кг.",9.26,3.48,3.34)
        self.point(s,"Связующее П-2",f"RC {nf(base['fixed'].reduced[1],0)} тыс. руб./т. Выпуск равен нулю.",9.26,4.84,3.34)
        self.box(s,"MILP подтверждена Fixed LP и независимой проверкой режимов пуска.",.59,6.5,12,.3,13,color=MUTED)

        s=self.slide("Цена инженерной надёжности",
                     "Истинная граница по полному перебору и сопоставление способов отбора",3)
        self.chart(s,"pareto",.47,2.0,8.65)
        k=d["knee"]
        if k:
            self.point(s,"Колено",f"{k['score']} баллов и {nf(k['npv'],0)} млн руб. NPV.",9.25,2.06,3.45)
        self.point(s,"Порог MCDA",f"{green.score} баллов за {nf(stress['green_npv_loss'],0)} млн руб. NPV относительно базы.",9.25,3.44,3.45)
        self.point(s,"Проверка метода",f"{len(d['pareto']['feasible'])} допустимых наборов из {d['pareto']['examined']} комбинаций.",9.25,4.91,3.45)
        self.box(s,"Точки фронта подписаны ID проектов. Источник — таблицы портфелей.",.6,6.5,12,.32,12,color=MUTED)

        s=self.slide("Два стресс-сценария",
                     "Секвестр и снижение NPV проектов · углеродный налог и обязательный балл",4)
        self.chart(s,"stress_portfolio",.62,1.98,9)
        self.point(s,"Секвестр",f"{ids(fin)} при бюджете {nf(sc.stress_budget,0)} млн руб. Остаток {nf(fin.slack,0)} млн.",9.55,2.27,3.2)
        self.point(s,"Углеродный налог",f"Минус {nf(stress['carbon_profit_loss'])} тыс. руб. за квартал. Выпуск сохраняется.",9.55,4.02,3.2)
        self.box(s,f"При MCDA ≥ {sc.score_floor} оптимальный допустимый портфель — {ids(green)}.",.62,6.48,12,.32,13,color=MUTED)

        s=self.slide("Решение к утверждению",
                     "Режим инвестиций зависит от обязательности порога надёжности",5)
        self.metric(s,.57,1.94,5.87,ids(green),f"При MCDA ≥ {sc.score_floor} · NPV {nf(green.npv,0)} млн руб.")
        self.metric(s,6.86,1.94,5.87,ids(exact),f"При финансовом приоритете · NPV {nf(exact.npv,0)} млн руб.")
        self.point(s,"Зависимости отраслевых проектов",
                   "Совместно финансировать азотную станцию и плазменную очистку при выборе экологического кластера.",.62,4.02,5.56)
        self.point(s,"Контроль операционного риска",
                   "Обеспечить квартальные квоты NMP и наномодификатора. Подготовить режим выпуска Э-1 при остановке экструдера.",6.91,4.02,5.57)
        self.box(s,f"Проверка расчётов · два решателя, полный перебор, {d['observed_tests']} тестов.",.63,6.53,12,.3,13,color=MUTED)
        self.prs.save(self.folder/PPTX)
