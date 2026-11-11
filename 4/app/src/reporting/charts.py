"""Charts read exported CSV, so reported numbers and plotted data share provenance."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .chart_validation import ChartValidationService
from ..io_utils import write_csv,write_json,sha256

COLORS={'DEU':'#2563a6','SRB':'#df8534','VNM':'#168b79'}

class ChartService:
    def write(self,tables: Path,destination: Path):
        destination.mkdir(parents=True,exist_ok=True); self.audits=[]; self.features=[]; self.paths=[]
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':120,'savefig.dpi':160,'axes.grid':True,'grid.alpha':.18,'axes.axisbelow':True})
        def read(name): return pd.read_csv(tables/(name+'.csv'))
        def save(fig,name,source,axes_data):
            fig.tight_layout(pad=1.5)
            checks=[ChartValidationService.validate_axis(ax,x,y) for ax,x,y in axes_data]
            path=destination/(name+'.png'); fig.savefig(path,facecolor='white',metadata={'Software':'FIP4 reproducible model'}); plt.close(fig)
            self.paths.append(path); self.audits.append(dict(chart_id=name,filename=path.name,source_table=source+'.csv',source_sha256=sha256(tables/(source+'.csv')),numeric_status='PASS',axes=checks,**ChartValidationService.image_geometry(path)))
        x=np.arange(3); labels=['DEU','SRB','VNM']
        risk=read('risk_rates'); fig,ax=plt.subplots(figsize=(9,5)); bottom=np.zeros(3)
        for key,label,color in [('wacc','WACC','#9aacbc'),('crp','CRP','#df8534'),('gpr','GPR','#2563a6')]:
            values=risk[key].to_numpy()*100; ax.bar(x,values,bottom=bottom,label=label,color=color); bottom+=values
        ax.set(xticks=x,xticklabels=labels,ylabel='% в год',title='Ставка дисконтирования: WACC + CRP + GPR'); ax.legend(ncol=3)
        save(fig,'01_risk','risk_rates',[(ax,x,bottom)])
        cap=read('capex'); fig,ax=plt.subplots(figsize=(9,5))
        ax.bar(x,cap['net']/1e6,label='Чистый CAPEX',color='#2563a6'); ax.bar(x,cap['subsidy_pv']/1e6,bottom=cap['net']/1e6,label='Ожидаемая PV субсидии',color='#69ad9b')
        ax.set(xticks=x,xticklabels=labels,ylabel='млн USD, t=0',title='Gross CAPEX = net CAPEX + PV субсидии'); ax.legend()
        save(fig,'02_capex','capex',[(ax,x,cap['gross']/1e6)])
        sup=read('supply_chains'); fig,ax=plt.subplots(figsize=(9,5))
        for i,(key,label,color) in enumerate([('raw_base','Базовое сырье','#9aacbc'),('raw_landed','Сырье с доставкой','#df8534'),('price_net','Чистая цена реализации','#2563a6')]): ax.bar(x+(i-1)*.25,sup[key],width=.25,label=label,color=color)
        ax.set(xticks=x,xticklabels=labels,ylabel='USD/м²',title='Удельные цены и сырье'); ax.legend(ncol=3,fontsize=9)
        save(fig,'03_supply','supply_chains',[(ax,x,sup[['raw_base','raw_landed','price_net']].to_numpy().ravel())])
        time=read('time_schedule'); fig,ax=plt.subplots(figsize=(10,5))
        for code in labels:
            d=time[time.country==code]; ax.plot(d.year,d.load,marker='o',label=code,color=COLORS[code])
            for t in [int(d[d.load>0].year.min()),int(d[d.load>0].year.max())]:
                value=float(d[d.year==t].load.iloc[0]); self.features.append(dict(chart_id='04_calendar',feature_type='operating_boundary',x=t,y=value,unit='year;fraction',method='exact extracted calendar',confidence_or_tolerance=0,economic_meaning=f'{code}: начало/конец эксплуатации'))
        ax.set(xticks=range(14),ylim=(-.08,1.20),ylabel='Доля годовой мощности',xlabel='Календарный год t',title='Загрузка: ровно 10 эквивалентных лет'); ax.legend(ncol=3)
        save(fig,'04_calendar','time_schedule',[(ax,time.year,time.load)])
        annual=read('annual_cashflows'); fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
        for ax,code in zip(axes,labels):
            d=annual[annual.country==code]
            ax.plot(d.year,d.local_cf/1e6,label='Local FCFF',marker='o',color='#9aacbc'); ax.plot(d.year,d.parent_cf/1e6,label='Parent CF',marker='.',color=COLORS[code])
            ax.set(title=code,ylabel='млн USD'); ax.axhline(0,color='#444444',lw=.7); ax.legend(loc='lower right')
        axes[-1].set(xlabel='Календарный год t',xticks=range(14))
        save(fig,'05_cashflows','annual_cashflows',[(ax,annual[annual.country==code].year,annual[annual.country==code][['local_cf','parent_cf']].to_numpy().ravel()/1e6) for ax,code in zip(axes,labels)])
        fig,ax=plt.subplots(figsize=(10,5))
        for code in labels:
            d=annual[annual.country==code]; ax.plot(d.year,d.cumulative_parent/1e6,marker='o',label=code,color=COLORS[code])
        ax.axhline(0,color='#444444',lw=1); ax.set(xticks=range(14),xlabel='Календарный год t',ylabel='млн USD, PV',title='Накопленный дисконтированный Parent CF'); ax.legend(ncol=3)
        save(fig,'06_cumulative','annual_cashflows',[(ax,annual.year,annual.cumulative_parent/1e6)])
        tax=read('taxation'); fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
        for code in labels:
            d=tax[(tax.country==code)&(tax.load>0)]; axes[0].plot(d.year,d.holiday_rate*100,marker='o',label=code,color=COLORS[code]); axes[1].plot(d.year,d.cash_tax/1e6,marker='o',label=code,color=COLORS[code])
        axes[0].set(ylabel='Ставка по режиму, %',title='Налоговые режимы и денежные выплаты CIT'); axes[0].legend(ncol=3)
        axes[1].set(ylabel='CIT, млн USD',xlabel='Календарный год t',xticks=range(14))
        active=tax[tax.load>0]
        save(fig,'07_taxation','taxation',[(axes[0],active.year,active.holiday_rate*100),(axes[1],active.year,active.cash_tax/1e6)])
        metric=read('base_metrics'); par=metric[metric.scope=='parent']; fig,axes=plt.subplots(1,3,figsize=(12,5))
        for ax,key,scale,title in zip(axes,['npv','irr','pi'],[1e6,.01,1],['Parent NPV, млн USD','Parent IRR, %','Parent PI']):
            ax.bar(x,par[key]/scale,color=[COLORS[c] for c in labels]); ax.axhline(0,color='#444444',lw=.7); ax.set(xticks=x,xticklabels=labels,title=title)
        save(fig,'08_metrics','base_metrics',[(ax,x,par[key]/scale) for ax,key,scale in zip(axes,['npv','irr','pi'],[1e6,.01,1])])
        stress=read('stress_metrics'); sx=np.arange(len(stress)); fig,ax=plt.subplots(figsize=(9,5))
        ax.bar(sx-.18,stress.base_npv/1e6,.36,label='База',color='#9aacbc'); ax.bar(sx+.18,stress.stress_npv/1e6,.36,label='Стресс',color='#bd5858')
        ax.set(xticks=sx,xticklabels=['VNM: Красный прилив','SRB: CBAM 8%'],ylabel='Parent NPV, млн USD',title='Два предписанных стресс-теста'); ax.legend()
        save(fig,'09_stress','stress_metrics',[(ax,sx,stress[['base_npv','stress_npv']].to_numpy().ravel()/1e6)])
        scenario=read('scenario_metrics'); fig,ax=plt.subplots(figsize=(10,5))
        for i,key in enumerate('ABC'):
            d=scenario[scenario.scenario==key]; vals=[float(d[d.country==c].npv.iloc[0])/1e6 for c in labels]
            ax.bar(x+(i-1)*.25,vals,.25,label={'A':'A: интеграция, p=0,20','B':'Б: база, p=0,50','C':'В: фрагментация, p=0,30'}[key])
        ax.set(xticks=x,xticklabels=labels,ylabel='Parent NPV, млн USD',title='Дискретные сценарии'); ax.legend(fontsize=9)
        save(fig,'10_scenarios','scenario_metrics',[(ax,x,scenario.npv/1e6)])
        stats=read('scenario_statistics'); fig,ax=plt.subplots(figsize=(9,5))
        for i,row in stats.iterrows(): ax.errorbar(i,row.expected/1e6,yerr=row['std']/1e6,fmt='o',capsize=9,color=COLORS[row.country],markersize=8)
        ax.set(xticks=x,xticklabels=labels,ylabel='млн USD',title='E[Parent NPV] ± σ: три дискретных сценария'); ax.axhline(0,color='#444444',lw=.7)
        save(fig,'11_expectation','scenario_statistics',[(ax,x,np.r_[(stats.expected-stats['std'])/1e6,(stats.expected+stats['std'])/1e6])])
        sensitivity=read('source_sensitivity'); fig,ax=plt.subplots(figsize=(10,5))
        for i,(key,label) in enumerate([('economic_npv','Экономическое правило'),('literal_wht_npv','Буквальная формула PDF')]): ax.bar(x+(i-.5)*.32,sensitivity[key]/1e6,.32,label=label)
        ax.set(xticks=x,xticklabels=labels,ylabel='Parent NPV, млн USD',title='Аудит противоречия WHT и повторного NWC'); ax.legend()
        save(fig,'12_source_audit','source_sensitivity',[(ax,x,sensitivity[['economic_npv','literal_wht_npv']].to_numpy().ravel()/1e6)])
        sen=read('sensitivities'); fig,axes=plt.subplots(2,2,figsize=(11,8))
        checks=[]
        for ax,key,title in zip(axes.flat,['igpr','wht','cbam','delay_year'],['Изменение IGPR, пункты','WHT, доля','CBAM, доля (только ЕС)','Дополнительная задержка, лет']):
            for code in labels:
                d=sen[(sen.parameter==key)&(sen.country==code)]; ax.plot(d.x,d.parent_npv/1e6,marker='o',color=COLORS[code],label=code)
                checks.append((ax,d.x,d.parent_npv/1e6))
            ax.set(xlabel=title,ylabel='Parent NPV, млн USD'); ax.legend(fontsize=8)
        fig.suptitle('Чувствительность: один фактор, остальные условия фиксированы')
        save(fig,'13_sensitivity','sensitivities',checks)
        # Record actual calendar events; no fabricated inflections or asymptotes.
        for code in labels:
            d=time[time.country==code]
            for _,row in d[d.nwc_cash_effect!=0].iterrows():
                self.features.append(dict(chart_id='04_calendar',feature_type='NWC_event_not_annotated',x=int(row.year),y=float(row.nwc_cash_effect),unit='year;USD',method='exact CSV event',confidence_or_tolerance=.01,economic_meaning=f'{code}: NWC вложение/возврат; отдельное событие, не перегиб'))
        write_csv(tables/'chart_features.csv',self.features)
        write_json(tables/'chart_validation.json',self.audits)
        return self.paths,self.audits
