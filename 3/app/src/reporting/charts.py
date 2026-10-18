"""Charts and numeric/layout audits; visual review is a separate hash-bound record."""
from dataclasses import asdict
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib.text import Text
from PIL import Image,ImageOps,ImageDraw
from ..io_utils import write_csv,sha256
from ..models import ChartAuditResult
from ..calculators.finance import CreditSpreadCalculator

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':13,
    'figure.dpi':100,'savefig.dpi':210,'axes.spines.top':False,'axes.spines.right':False})
BLUE='#2864a0'; RED='#bb4a45'; GREEN='#21866b'


class ChartValidationService:
    @staticmethod
    def match_values(artist,expected):
        if hasattr(artist,'get_ydata'):
            actual=artist.get_ydata(orig=False)
        elif hasattr(artist,'get_offsets'):
            actual=np.asarray(artist.get_offsets())[:,1]
        else:
            actual=[patch.get_height() for patch in artist.patches]
        actual=np.asarray(actual,dtype=float); expected=np.asarray(expected,dtype=float)
        if actual.shape!=expected.shape or not np.allclose(actual,expected,rtol=1e-10,atol=1e-12):
            raise ValueError('Plotted series differs from source table')

    @staticmethod
    def audit(fig,chart_id):
        fig.canvas.draw(); renderer=fig.canvas.get_renderer()
        width,height=fig.canvas.get_width_height()
        outside=[]; points=0; nonfinite=[]
        unused_tick_labels=set()
        for ax in fig.axes:
            for axis,limits in ((ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())):
                low,high=sorted(limits)
                for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                    if not low<=tick.get_loc()<=high:
                        unused_tick_labels.update((tick.label1,tick.label2))
            for line in ax.lines:
                xy=line.get_xydata()
                if not np.isfinite(xy).all(): nonfinite.append(line.get_label())
                points+=len(xy)
            for collection in ax.collections:
                offsets=np.asarray(collection.get_offsets(),dtype=float)
                if not np.isfinite(offsets).all(): nonfinite.append('scatter')
                points+=len(offsets)
        for item in fig.findobj(match=Text):
            if item in unused_tick_labels or not item.get_visible() or not item.get_text(): continue
            box=item.get_window_extent(renderer)
            if box.x0 < -2 or box.y0 < -2 or box.x1 > width+2 or box.y1 > height+2:
                outside.append(item.get_text())
        checks=dict(nonfinite=nonfinite,outside_text=outside,points=points,width=width,height=height)
        return ChartAuditResult(chart_id,'FAIL' if outside or nonfinite else 'PASS',checks)


class ChartWriter:
    def __init__(self,output: Path,logger):
        self.output=output; self.logger=logger
        self.charts=output/'charts'; self.tables=output/'tables'
        self.charts.mkdir(parents=True,exist_ok=True)
        self.catalog=[]
        review=output.parent/'docs/visual_review.json'
        self.reviews=json.loads(review.read_text(encoding='utf-8')) if review.exists() else {}

    def save(self,fig,name,table,caption,interpretation,metrics,points=None):
        source=self.tables/f'chart_{name}.csv'
        table.to_csv(source,index=True,encoding='utf-8-sig')
        audit=ChartValidationService.audit(fig,name)
        self.logger.log('chart_validation',f'{name}: {audit.validation_status}; {audit.checks}')
        if audit.validation_status!='PASS':
            self.logger.issue(name,'charts','Проверить границы графика','ChartValidationService.audit',
                str(audit.checks),'Геометрия/данные рисунка','Требуется корректировка размеров','FAIL','implementation error')
            plt.close(fig)
            raise ValueError(f'Chart audit failed: {name}: {audit.checks}')
        path=self.charts/f'{name}.png'
        fig.savefig(path,dpi=210,facecolor='white')
        plt.close(fig)
        with Image.open(path) as image:
            image.verify()
        digest=sha256(path)
        visual='PASS' if self.reviews.get(name,{}).get('sha256')==digest else 'NOT_VERIFIED'
        self.catalog.append(dict(chart_id=name,dataset=str(source.relative_to(self.output)),
            metric_ids=metrics,validation_status='PASS',visual_status=visual,caption=caption,
            interpretation=interpretation,main_observation=interpretation,economic_conclusion=interpretation,
            annotated_points=json.dumps(points or [],ensure_ascii=False),
            source_paths=str(source.relative_to(self.output)),png_path=str(path.relative_to(self.output)),sha256=digest))

    @staticmethod
    def figure(title,xlabel='',ylabel=''):
        fig,ax=plt.subplots(figsize=(10,5.8),layout='constrained')
        ax.set(title=title,xlabel=xlabel,ylabel=ylabel); ax.grid(axis='y',alpha=.2)
        return fig,ax

    def build(self,prices,returns,regression,base,stress,p,s,waterfall,discount,diagnostics):
        b=base.metrics; c=stress.metrics
        fig,ax=self.figure('Месячные доходности: HXL относительно S&P 500','S&P 500, доходность за месяц','HXL, доходность за месяц')
        x=returns['^GSPC'].to_numpy(); y=returns['HXL'].to_numpy()
        scatter=ax.scatter(x,y,s=26,color=BLUE,alpha=.75,label=f'Наблюдения, n={regression.n}')
        ChartValidationService.match_values(scatter,returns.HXL)
        line_x=np.array([x.min(),x.max()]); ax.plot(line_x,regression.alpha_raw+regression.beta_ols*line_x,color=RED,label='OLS')
        ax.xaxis.set_major_formatter(PercentFormatter(1)); ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.text(.02,.98,f'β = {regression.beta_ols:.4f}\nα raw = {regression.alpha_raw:.4%}\nR² = {regression.r_squared:.4f}',
            transform=ax.transAxes,va='top',bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
        ax.legend(loc='lower right')
        self.save(fig,'01_ols',returns,'Рисунок 1. OLS на полных месячных доходностях.',
            f'Рынок объясняет {regression.r_squared:.1%} вариации доходностей HXL. β={regression.beta_ols:.4f}; это диагностическая оценка, основной WACC использует β аналога 1.25.', 'beta_ols,alpha_raw,r_squared')
        normalized=prices[['HXL','^GSPC']]/prices[['HXL','^GSPC']].iloc[0]*100
        normalized.index=pd.DatetimeIndex(prices.Date,name='Date')
        fig,ax=self.figure('Динамика предоставленных скорректированных цен','Дата','Индекс цены: первая дата = 100')
        for col,color in [('HXL',BLUE),('^GSPC',RED)]:
            line,=ax.plot(normalized.index,normalized[col],label=col,color=color)
            ChartValidationService.match_values(line,normalized[col])
        ax.legend(); self.save(fig,'02_prices',normalized,'Рисунок 2. Цены приведены к общей базе 100.',
            f'К конечной дате индекс HXL={normalized.HXL.iloc[-1]:.1f}, S&P 500={normalized["^GSPC"].iloc[-1]:.1f}. Это динамика двух активов, а не подтверждение происхождения adjusted close.','HXL,^GSPC')
        fig,ax=self.figure('Месячные доходности и сохранённые экстремумы','Месяц','Простая доходность')
        ax.plot(returns.index,returns['HXL'],color=BLUE,label='HXL'); ax.plot(returns.index,returns['^GSPC'],color=RED,label='S&P 500')
        for line,col in zip(ax.lines,('HXL','^GSPC')): ChartValidationService.match_values(line,returns[col])
        lo=returns['HXL'].idxmin(); hi=returns['HXL'].idxmax()
        ax.scatter([lo,hi],[returns.loc[lo,'HXL'],returns.loc[hi,'HXL']],color='black',s=40,zorder=4,label='min/max HXL')
        ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend()
        points=[dict(kind=k,date=str(d.date()),value=float(returns.loc[d,'HXL'])) for k,d in [('min',lo),('max',hi)]]
        self.save(fig,'03_returns',returns,'Рисунок 3. Месячные доходности без удаления выбросов.',
            f'Минимум HXL {returns.loc[lo,"HXL"]:.2%} ({lo.date()}), максимум {returns.loc[hi,"HXL"]:.2%} ({hi.date()}); выбросы сохранены.','monthly_returns',points)
        rate_table=pd.DataFrame({'base':[b[k] for k in ('wacc','ke','kd','kd_after_tax')],
                                 'stress':[c[k] for k in ('wacc','ke','kd','kd_after_tax')]},index=['WACC','Ke','Kd','Kd после налога'])
        fig,ax=self.figure('Стоимость капитала: базовый сценарий и поликризис','Метрика','Годовая ставка, USD')
        positions=np.arange(4); ax.bar(positions-.19,rate_table.base,.38,label='База',color=BLUE)
        ax.bar(positions+.19,rate_table.stress,.38,label='Поликризис',color=RED)
        for bars,col in zip(ax.containers,('base','stress')): ChartValidationService.match_values(bars,rate_table[col])
        ax.set_xticks(positions,rate_table.index); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend()
        self.save(fig,'04_rates',rate_table,'Рисунок 4. Сравнение стоимости источников финансирования.',
            f'WACC возрастает с {b["wacc"]:.2%} до {c["wacc"]:.2%}, на {(c["wacc"]-b["wacc"])*100:.2f} п.п. Налоговый щит применён один раз.','wacc,ke,kd,kd_after_tax')
        fig,axes=plt.subplots(1,2,figsize=(11,5.8),layout='constrained')
        cap=pd.DataFrame({'base':[b[k] for k in ('de','beta_u','beta_l','we','wd')],
                          'stress':[c[k] for k in ('de','beta_u','beta_l','we','wd')]},index=['D/E','β U','β L','we','wd'])
        for ax,selection,title in [(axes[0],slice(0,3),'Рычаг и бета'),(axes[1],slice(3,5),'Веса капитала')]:
            t=cap.iloc[selection]; xx=np.arange(len(t)); ax.bar(xx-.18,t.base,.36,label='База',color=BLUE)
            ax.bar(xx+.18,t.stress,.36,label='Поликризис',color=RED); ax.set_xticks(xx,t.index); ax.set_title(title); ax.legend(); ax.grid(axis='y',alpha=.2)
            for bars,col in zip(ax.containers,('base','stress')): ChartValidationService.match_values(bars,t[col])
        axes[1].yaxis.set_major_formatter(PercentFormatter(1))
        self.save(fig,'05_capital',cap,'Рисунок 5. Сжатие капитала увеличивает долговой рычаг.',
            f'E сокращается на {c["delta_total"]:.0%}, D неизменен; D/E={c["de"]:.4f}, вес долга={c["wd"]:.2%}. Масштаб CAPEX используется как условная начальная оценка.','de,beta_u,beta_l,we,wd')
        dscr=np.linspace(1,p.covenant+.3,181)
        spreads=np.array([CreditSpreadCalculator.calculate(float(v),p.covenant,s.gamma1) for v in dscr])
        credit=pd.DataFrame({'dscr':dscr,'spread':spreads})
        fig,ax=self.figure('Кредитный спред и пороги покрытия долга','DSCR, x','Дополнительный годовой спред')
        line,=ax.plot(dscr,spreads,color=BLUE,label='Определённая ветвь')
        ChartValidationService.match_values(line,credit.spread)
        ax.axvline(1,color='black',linestyle=':',label='Технический дефолт: DSCR < 1')
        ax.axvline(p.covenant,color=GREEN,linestyle='--',label=f'Ковенанта {p.covenant:.2f}x')
        ax.scatter([c['dscr']],[c['credit_spread']],color=RED,s=60,label=f'Кризис: {c["dscr"]:.3f}x')
        ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend()
        critical_mu=1-p.covenant/p.dscr0
        self.save(fig,'06_credit',credit,'Рисунок 6. Кусочная функция кредитного штрафа.',
            f'Штраф {c["credit_spread"]:.4%}; ковенанта нарушается при сжатии EBITDA выше {critical_mu:.2%}. Ниже DSCR=1 численная ветвь не задана.',
            'dscr,credit_spread',[dict(kind='covenant',dscr=p.covenant,spread=0,mu_ebitda=critical_mu),dict(kind='default_boundary',dscr=1,spread=s.gamma1*(p.covenant-1)),dict(kind='crisis',dscr=c['dscr'],spread=c['credit_spread'])])
        fig,ax=self.figure('Waterfall: иллюстративный каскад с сохранением долга','Очередность платежей','млн USD / год')
        flows=waterfall.flows; cumul=0; wf_rows=[]
        for i,row in enumerate(flows):
            value=row['amount']; bottom=cumul if value>=0 else cumul+value
            bars=ax.bar(i,abs(value),bottom=bottom,color=BLUE if value>=0 else RED,width=.65)
            ChartValidationService.match_values(bars,[abs(row['amount'])])
            if i: ax.plot([i-1+.325,i-.325],[cumul,cumul],color='gray',linestyle='--',linewidth=.8)
            label='0.00' if value==0 else f'{value:+.2f}'
            ax.text(i,bottom+abs(value)/2,label,ha='center',va='center',fontsize=9,
                bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=1))
            wf_rows.append(dict(label=row['label'],amount=value,bottom=bottom,end=cumul+value)); cumul+=value
        ax.bar(len(flows),waterfall.retained,color=GREEN,width=.65)
        labels=['Выручка','OPEX','Налоги\n(сценарий)','Долг','DSRA\n(сценарий)','Дивиденды','Остаток']
        ax.set_xticks(range(len(labels)),labels); ax.margins(y=.12)
        if not math.isclose(cumul,waterfall.retained,abs_tol=1e-9): raise ValueError('Waterfall balance')
        self.save(fig,'07_waterfall',pd.DataFrame(wf_rows),'Рисунок 7. Иллюстрация: налог=0, выручка неизменна, OPEX — остаточная величина.',
            f'EBITDA={c["ebitda"]:.2f}, долг выплачен {waterfall.debt_paid:.2f}, остаток {waterfall.cash_after_debt_service:.2f} направлен в DSRA. Дивиденды заблокированы. Фактические налоги и требуемый DSRA неизвестны.',
            'ebitda,debt_paid,dsra,dividends,retained')
        fig,ax=self.figure('Дисконтирование единичного будущего потока','Год получения одного USD','Текущая стоимость, USD')
        for col,color,label in [('base_factor',BLUE,'База'),('stress_factor',RED,'Поликризис')]:
            line,=ax.plot(discount.year,discount[col],marker='o',color=color,label=label)
            ChartValidationService.match_values(line,discount[col])
        ax.legend()
        self.save(fig,'08_discount',discount,'Рисунок 8. Коэффициенты дисконтирования за 10 лет; не прогноз FCF.',
            f'На 10-м году один USD стоит {discount.base_factor.iloc[-1]:.4f} в базе и {discount.stress_factor.iloc[-1]:.4f} в кризисе. Без FCF нельзя определить NPV/IRR.','discount_factor')
        fig,ax=self.figure('Изолированные шоки и их совместное действие','Диагностический сценарий','WACC, годовая ставка USD')
        bars=ax.bar(diagnostics.scenario,diagnostics.wacc,color=[BLUE]*7+[RED])
        ChartValidationService.match_values(bars,diagnostics.wacc)
        ax.tick_params(axis='x',labelrotation=20); ax.yaxis.set_major_formatter(PercentFormatter(1))
        self.save(fig,'09_shocks',diagnostics,'Рисунок 9. Изолированные шоки служат диагностикой; основной результат — совместный.',
            'Совместная модель включает произведение пошлин и энергошока, динамические веса и нелинейный кредитный штраф. Сумма изолированных эффектов не равна общему эффекту.','wacc,shock_diagnostics')
        write_csv(self.tables/'chart_catalog.csv',self.catalog)
        self.montage()
        return self.catalog

    def montage(self):
        canvas=Image.new('RGB',(1800,1200),'white')
        for i,row in enumerate(self.catalog):
            with Image.open(self.output/row['png_path']) as img:
                thumb=ImageOps.contain(img,(600,390)); canvas.paste(thumb,((i%3)*600,(i//3)*400))
        canvas.save(self.charts/'review_montage.png')
