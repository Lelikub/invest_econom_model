import hashlib
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from ..repositories import read_csv,write_csv

BLUE="#126788"
NAVY="#17364D"
TEAL="#188075"
AMBER="#B65E24"
LIGHT="#A6C5D0"
MARK="#B94363"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ChartService:
    def __init__(self,tables,charts,review):
        self.tables=tables
        self.charts=charts
        self.review=json.loads(review.read_text(encoding="utf-8")) if review.is_file() else {}
        self.catalog=[]

    def load(self,name):
        return read_csv(self.tables/(name+".csv"))

    @staticmethod
    def values(rows,key):
        values=[float(r[key]) for r in rows]
        if not all(map(math.isfinite,values)) or not values:
            raise ValueError(f"Chart column has no finite series: {key}")
        return values

    def save(self,fig,name,sources,expected,units):
        fig.canvas.draw()
        actual=0
        for ax in fig.axes:
            actual+=sum(len(line.get_xdata()) for line in ax.lines)
            actual+=sum(len(c.get_offsets()) for c in ax.collections)
            actual+=len(ax.patches)
            if not all(map(math.isfinite,(*ax.get_xlim(),*ax.get_ylim()))) or not ax.get_xlabel() or not ax.get_ylabel():
                raise RuntimeError(f"Missing chart axis information: {name}")
            xmin,xmax=ax.get_xlim(); ymin,ymax=ax.get_ylim()
            checked_points=[(float(x),float(y)) for line in ax.lines for x,y in zip(line.get_xdata(orig=False),line.get_ydata(orig=False))]
            checked_points.extend((float(x),float(y)) for collection in ax.collections for x,y in collection.get_offsets())
            for bar in ax.patches:
                checked_points.extend(((bar.get_x(),bar.get_y()),
                                       (bar.get_x()+bar.get_width(),bar.get_y()+bar.get_height())))
            if not all(math.isfinite(x) and math.isfinite(y) and xmin-1e-7<=x<=xmax+1e-7 and ymin-1e-7<=y<=ymax+1e-7
                       for x,y in checked_points):
                raise RuntimeError(f"Chart coordinates clipped or non-finite: {name}")
        if expected!=actual:
            raise RuntimeError(f"{name}: {actual} artists plotted, expected {expected}")
        fig.tight_layout(pad=1.25)
        fig.canvas.draw()
        bbox=fig.get_tightbbox(fig.canvas.get_renderer())
        if bbox.x0<0 or bbox.y0<0 or bbox.x1>fig.get_figwidth()+.02 or bbox.y1>fig.get_figheight()+.02:
            raise RuntimeError(f"Chart labels outside canvas: {name}")
        path=self.charts/(name+".png")
        fig.savefig(path,dpi=155,facecolor="white",metadata={"Software":"Matplotlib"})
        plt.close(fig)
        with Image.open(path) as image:
            size=image.size
            image.verify()
        for source in sources:
            if not (self.tables/source).is_file():
                raise FileNotFoundError(source)
        digest=sha(path)
        review=self.review.get(name,{})
        verified=review.get("sha256")==digest and review.get("status")=="PASS" and bool(review.get("reviewer"))
        self.catalog.append(dict(chart=path.name,source_csv="; ".join(sources),source_sha256="; ".join(sha(self.tables/s) for s in sources),
              units=units,points=actual,width_px=size[0],height_px=size[1],sha256=digest,
              automatic="PASS",visual="PASS" if verified else "VISUAL_NOT_VERIFIED",
              conclusion=review.get("conclusion","") if verified else "Требуется просмотр PNG"))

    @staticmethod
    def style(ax,title,x,y):
        ax.set_title(title,loc="left",weight="bold",color=NAVY,pad=10)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.grid(axis="y",alpha=.23)
        ax.set_axisbelow(True)
        ax.spines[["top","right"]].set_visible(False)

    def run(self):
        plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.labelcolor":NAVY,
                           "xtick.color":NAVY,"ytick.color":NAVY,"legend.frameon":False})
        self.charts.mkdir(parents=True,exist_ok=True)
        resources=self.load("resources")
        milp=[r for r in resources if r["case"]=="MILP"]
        fixed=[r for r in resources if r["case"]=="Fixed LP"]
        products=[r for r in self.load("production") if r["case"]=="MILP"]
        labels=["Агр. 1","Агр. 2","Агр. 3","NMP","Наномод."]
        fig,ax=plt.subplots(1,2,figsize=(9,3.1))
        for i,r in enumerate(products):
            vol=self.values([r],"good")[0]; gross=self.values([r],"gross")[0]
            ax[0].bar(i-.17,vol,.33,color=BLUE,label="Кондиционный" if i==0 else None)
            ax[0].bar(i+.17,gross,.33,color=LIGHT,label="Валовый" if i==0 else None)
        ax[0].set_xticks(range(len(products)),[p["product"] for p in products])
        ax[0].legend(loc="upper center",ncol=2,fontsize=8)
        ax[0].set_ylim(0,max(self.values(products,"gross"))*1.23)
        ax[1].bar(labels,[v*100 for v in self.values(milp,"utilization")],color=[BLUE]*3+[TEAL]*2)
        ax[1].set_ylim(0,112)
        self.style(ax[0],"Программа производства","Продукт","Тонн за квартал")
        self.style(ax[1],"Загрузка ресурсов","Ресурс","% физического лимита")
        self.save(fig,"production",["production.csv","resources.csv"],11,"т; %")

        rows=self.load("effective")
        norms=[r for r in rows if r["product"]=="П-2" and r["resource_unit"]=="маш.-ч"]
        fig,ax=plt.subplots(figsize=(8,2.65))
        ax.bar(labels[:len(norms)],self.values(norms,"raw"),color=BLUE,label="При Y = 1")
        ax.bar(labels[:len(norms)],self.values(norms,"extra"),bottom=self.values(norms,"raw"),color=AMBER,label="Из-за потерь выхода")
        ax.legend(loc="upper right")
        ax.set_ylim(0,max(self.values(norms,"effective"))*1.42)
        self.style(ax,"Эффект выхода годного у П-2","Агрегат","Маш.-ч / т готового")
        self.save(fig,"effective",["effective.csv"],2*len(norms),"маш.-ч/т")

        fig,ax=plt.subplots(1,2,figsize=(9,3.0))
        ax[0].bar(labels,[100*v for v in self.values(fixed,"utilization")],color=BLUE)
        ax[0].set_ylim(0,112)
        dual=self.values(fixed,"shadow")
        ax[1].bar(labels,dual,color=[BLUE]*3+[TEAL]*2)
        for i,v in enumerate(dual):
            ax[1].annotate(f"{v:g}",(i,v),xytext=(0,4),textcoords="offset points",ha="center")
        ax[1].set_ylim(0,max(1,*dual)*1.16)
        self.style(ax[0],"Fixed LP · остаток до 100%","Ресурс","Загрузка, %")
        self.style(ax[1],"Fixed LP · теневые цены","Ресурс","тыс. руб. / ед. ресурса")
        self.save(fig,"duals",["resources.csv"],10,"%; тыс. руб./маш.-ч, л или кг")

        op=self.load("operations")
        fig,ax=plt.subplots(figsize=(8,2.7))
        profits=[v/1000 for v in self.values(op,"profit")]
        ax.bar([r["case"] for r in op],profits,color=[LIGHT,BLUE,TEAL])
        for i,v in enumerate(profits):
            ax.annotate(f"{v:.3f}",(i,v),xytext=(0,4),textcoords="offset points",ha="center")
        ax.set_ylim(0,max(profits)*1.14)
        self.style(ax,"Прибыль и фиксированные пуски","Модель","млн руб. / квартал")
        self.save(fig,"operations",["operations.csv"],len(op),"млн руб./квартал")

        pc=self.load("portfolio_comparison")
        fig,ax=plt.subplots(figsize=(8,2.8))
        for i,r in enumerate(pc):
            ax.bar(i-.16,float(r["npv"]),.31,color=TEAL,label="NPV" if i==0 else None)
            ax.bar(i+.16,float(r["capex"]),.31,color=LIGHT,label="CAPEX" if i==0 else None)
        ax.set_xticks(range(len(pc)),[r["method"] for r in pc])
        ax.legend(loc="upper right")
        ax.set_ylim(0,max(self.values(pc,"capex"))*1.25)
        self.style(ax,"Жадный отбор и целочисленный оптимум","Метод","млн руб.")
        self.save(fig,"portfolio",["portfolio_comparison.csv"],2*len(pc),"млн руб.")

        all_=self.load("pareto_all_feasible")
        front=self.load("pareto_nondominated")
        eps=self.load("epsilon_solutions")
        weighted=self.load("weighted_solutions")
        ep=sorted({(float(r["score"]),float(r["npv"])) for r in eps})
        wp=sorted({(float(r["score"]),float(r["npv"])) for r in weighted})
        fig,ax=plt.subplots(figsize=(8.5,3.35))
        ax.scatter(self.values(all_,"score"),self.values(all_,"npv"),s=22,color=LIGHT,label="Допустимые портфели")
        ax.plot(self.values(front,"score"),self.values(front,"npv"),"o--",color=NAVY,lw=1.25,label="Истинный фронт")
        ax.scatter(*zip(*ep),s=110,facecolors="none",edgecolors=TEAL,marker="s",label="ε-ограничения")
        ax.scatter(*zip(*wp),s=61,color=AMBER,marker="x",zorder=5,label="Взвешенная сумма")
        for r in front:
            ax.annotate(r["ids"],(float(r["score"]),float(r["npv"])),xytext=(0,9),textcoords="offset points",ha="center",fontsize=8)
        ax.set_xlim(-12,max(self.values(all_,"score"))+34)
        ax.set_ylim(-5,max(self.values(all_,"npv"))+24)
        ax.legend(loc="upper left",fontsize=8)
        self.style(ax,"Граница прибыльности и надёжности","Инженерно-экологический балл (MCDA)","NPV, млн руб.")
        self.save(fig,"pareto",["pareto_all_feasible.csv","pareto_nondominated.csv","epsilon_solutions.csv","weighted_solutions.csv"],
                  len(all_)+len(front)+len(ep)+len(wp),"балл; млн руб.")

        mrt=self.load("mrt")
        knee=self.load("knee")
        if mrt:
            fig,ax=plt.subplots(figsize=(8,2.75))
            ax.bar([f"{r['from_score']} → {r['to_score']}" for r in mrt],self.values(mrt,"mrt"),
                   color=[TEAL if r["efficient"]=="True" else AMBER for r in mrt])
            for i,r in enumerate(mrt):
                ax.annotate(f"{float(r['mrt']):.3f}",(i,float(r["mrt"])),xytext=(0,5),textcoords="offset points",ha="center")
            for row in knee:
                if row.get("knee_status")=="KNEE":
                    index=next(i for i,r in enumerate(mrt) if r["to_score"]==row["score"])
                    ax.annotate("Колено",(index,.39),ha="center",color=NAVY,weight="bold")
            ax.set_ylim(0,max(.46,max(self.values(mrt,"mrt"))*1.2))
            self.style(ax,"Уступка NPV за дополнительный балл","Соседние портфели по MCDA","млн руб. / балл")
            self.save(fig,"mrt",["mrt.csv","knee.csv"],len(mrt),"млн руб./балл")

        edge=[r for r in self.load("edge_cases") if r["objective"]]
        fig,ax=plt.subplots(figsize=(8,2.65))
        ax.bar([r["case"] for r in edge],[v/1000 for v in self.values(edge,"objective")],color=[LIGHT,TEAL,AMBER])
        self.style(ax,"Три производственных граничных случая","Сценарий","млн руб. / квартал")
        self.save(fig,"edges",["edge_cases.csv"],len(edge),"млн руб./квартал")

        sp=self.load("stress_portfolio")
        fig,ax=plt.subplots(1,2,figsize=(9,2.85))
        for a,key,unit in zip(ax,("npv","score"),("NPV, млн руб.","Баллы MCDA")):
            a.bar([r["case"] for r in sp],self.values(sp,key),color=[BLUE,AMBER,TEAL])
            self.style(a,"Инвестиционный стресс","Сценарий",unit)
        self.save(fig,"stress_portfolio",["stress_portfolio.csv"],2*len(sp),"млн руб.; баллы")

        tax=self.load("stress_operations")
        fig,ax=plt.subplots(figsize=(8,2.65))
        ax.bar([r["product"] for r in tax],self.values(tax,"tax_paid"),color=[BLUE,LIGHT,TEAL])
        self.style(ax,"Начисление углеродного налога","Продукт","тыс. руб. / квартал")
        self.save(fig,"stress_carbon",["stress_operations.csv","stress_profit.csv"],len(tax),"тыс. руб./квартал")
        write_csv(self.tables/"chart_catalog.csv",self.catalog)
        return self.catalog
