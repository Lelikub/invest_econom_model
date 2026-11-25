import json
import math
from pathlib import Path
import subprocess
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as col

from ..repositories import write_csv

CHECK_TOL = 1e-5


def sheet(wb, name, rows):
    ws = wb.create_sheet(name)
    for row in rows:
        ws.append(row)
    return ws


def format_book(wb):
    for ws in wb:
        ws.freeze_panes = "B2"
        for cell in ws[1]:
            cell.fill = PatternFill("solid",fgColor="17364D")
            cell.font = Font(bold=True,color="FFFFFF")
            cell.alignment = Alignment(vertical="center",wrap_text=True)
        ws.row_dimensions[1].height = 30
        for column in ws.columns:
            length = max((len(str(c.value)) for c in column if c.value is not None and c.data_type!="f"),default=10)
            ws.column_dimensions[column[0].column_letter].width = min(54,max(12,length+2))
            for cell in column[1:]:
                if cell.data_type=="f" or isinstance(cell.value,float):
                    cell.number_format = "0.000000"
        ws.sheet_view.showGridLines = False


def number_row(ws,row=2, start=2,end=7):
    return f"{col(start)}{row}:{col(end)}{row}"


class WorkbookService:
    def build(self,path,op,pf,sc,base,source,pareto=None,stress=None):
        wb=Workbook()
        wb.remove(wb.active)
        checks=[]
        def check(ws, cell, value, unit, kind="worksheet"):
            checks.append(dict(check=f"{ws.title}!{cell}",sheet=ws.title,cell=cell,python_value=float(value),
                               unit=unit,tolerance=CHECK_TOL,source=kind))

        sheet(wb,"Source", [tuple(source[0])] + [tuple(row.values()) for row in source])
        sheet(wb,"Products", [("Product","Э-1","П-2","К-3"),("Yield",*(p.yield_rate for p in op.products)),
                             ("Margin, тыс. руб./т",*(p.margin for p in op.products)),
                             ("Fixed cost, тыс. руб.",*(m.fixed_cost for m in op.machines))])
        labels=("Агрегат 1","Агрегат 2","Агрегат 3","NMP","Наномодификатор")
        raw=sheet(wb,"RawResources",[("Resource","Э-1","П-2","К-3","Capacity","Unit")])
        for label, row, resource, unit in zip(labels,op.machine_coefficients+op.material_coefficients,
                                             op.machines+op.materials,("маш.-ч",)*3+("л","кг")):
            raw.append((label,*row,resource.capacity,unit))
        eff=sheet(wb,"Effective",[("Resource","Э-1","П-2","К-3","Capacity","Unit","Extra П-2 / т")])
        for i,row in enumerate(op.machine_coefficients+op.material_coefficients,2):
            eff.append((f"=RawResources!A{i}",*(f"=RawResources!{c}{i}/Products!{c}$2" for c in "BCD"),
                        f"=RawResources!E{i}",f"=RawResources!F{i}",f"=C{i}-RawResources!C{i}"))
            for j,value in enumerate(row,2):
                check(eff,f"{col(j)}{i}",value/op.products[j-2].yield_rate,"ресурс/т")
            check(eff,f"G{i}",row[1]*(1/op.products[1].yield_rate-1),"ресурс/т")
        projects=sheet(wb,"Projects",[("ID","Name","CAPEX, млн","NPV, млн","MCDA")])
        for p in pf.projects:
            projects.append((p.id,p.name,p.capex,p.npv,p.score))
        sheet(wb,"Settings",[("Parameter","Value"),("Budget",pf.budget),("Stress budget",sc.stress_budget),
                            ("NPV cut",sc.npv_cut),("Carbon tax, руб.",sc.carbon_tax),("Emissions factor",sc.emission_factor),
                            ("Score floor",sc.score_floor),("Gap fraction",sc.gap_limit)])
        for name,key in (("LP","lp"),("MILP","milp"),("Fixed LP","fixed")):
            solved=base[key]
            ws=self.operation_sheet(wb,name,solved,labels)
            for c,value in zip("BCDEFG",solved.x+solved.y):
                check(ws,c+"2",value,"т" if c in "BCD" else "доля","Excel Solver")
            check(ws,"B3",solved.objective,"тыс. руб.","Excel Solver")
            for row,(load,rhs,slack) in enumerate(zip(solved.load,solved.rhs,solved.slack),5):
                for col_,value in zip("BCD",(load,rhs,slack)):
                    check(ws,f"{col_}{row}",value,"ед. ресурса")
        pi=sheet(wb,"PI",[("ID","CAPEX","NPV","PI")])
        for i,p in enumerate(pf.projects,2):
            pi.append((f"=Projects!A{i}",f"=Projects!C{i}",f"=Projects!D{i}",f"=1+C{i}/B{i}"))
            check(pi,f"D{i}",1+p.npv/p.capex,"ratio")
        for name,key in (("Greedy","greedy"),("Knapsack","exact"),("Enumeration","enumeration")):
            ws=self.portfolio_sheet(wb,name,base[key])
            for cell,value,unit in (("B3",base[key].npv,"млн руб."),("B4",base[key].capex,"млн руб."),
                                    ("B5",base[key].score,"балл"),("B6",base[key].slack,"млн руб."),
                                    ("B8",1,"bool"),("B9",0,"bool"),("B10",0,"bool"),("B11",0,"bool")):
                expected = value
                if cell=="B8": expected=int(2 in base[key].ids)+int(3 in base[key].ids)
                if cell=="B9": expected=int(4 in base[key].ids)-int(1 in base[key].ids)
                check(ws,cell,expected,unit,"Excel Solver" if key=="exact" and cell in {"B3","B4","B5","B6"} else "worksheet")
            if key=="exact":
                for i in range(1,8):
                    check(ws,f"{col(i+1)}2",i in base[key].ids,"bool","Excel Solver")
        greedy=wb["Greedy"]
        greedy.append(("Step project","PI","Bundle","Decision","CAPEX after"))
        for entry in base["greedy_attempts"]:
            i=entry["id"]
            greedy.append((i,f"=PI!D{i+1}",entry["bundle"],entry["decision"],entry["capex_after"]))
        all_bits=self.binary_sheet(wb)
        check(all_bits,"Q2",base["enumeration"].npv,"млн руб.")
        check(all_bits,"Q3",base["feasible_count"],"портфель")
        compare=sheet(wb,"Comparison",[("Method","NPV","CAPEX","Score","Slack","Gap to exact")])
        for i,name in enumerate(("Greedy","Knapsack","Enumeration"),2):
            compare.append((name,*(f"={name}!B{r}" for r in (3,4,5,6)),f"=$B$3-B{i}"))
        if pareto is not None and stress is not None:
            self.add_analysis(wb,pf,pareto,stress,check,op,sc)
        format_book(wb)
        wb.save(path)
        return checks

    @staticmethod
    def operation_sheet(wb,name,solved,labels):
        ws=sheet(wb,name,[("Variable","Э-1","П-2","К-3","y1","y2","y3"),("Solution",*solved.x,*solved.y),
                          ("Profit, тыс. руб.","=SUMPRODUCT(B2:D2,Products!B3:D3)-SUMPRODUCT(E2:G2,Products!B4:D4)"),
                          ("Resource","Load","RHS","Slack","SciPy LP dual","Dual × slack")])
        for i,label in enumerate(labels,5):
            row=i-3
            rhs=f"=Effective!E{row}*{col(i)}$2" if i<=7 else f"=Effective!E{row}"
            shadow=solved.shadow[i-5] if solved.shadow else None
            ws.append((label,f"=SUMPRODUCT($B$2:$D$2,Effective!B{row}:D{row})",rhs,f"=C{i}-B{i}",shadow,
                       f"=D{i}*E{i}" if shadow is not None else None))
        if solved.shadow:
            upper = solved.upper_shadow or (0,0,0)
            ws.append(("RC production", *(f"=Products!{c}3-SUMPRODUCT(Effective!{c}2:{c}6,$E$5:$E$9)" for c in "BCD")))
            ws.append(("x × RC", *(f"={c}2*{c}10" for c in "BCD")))
            ws.append(("SciPy upper bound duals",*upper))
            if solved.upper_shadow:
                ws.append(("RC launch",*(f"=-Products!{c}4+Effective!E{i}*E{i+3}-{c}12" for i,c in enumerate("BCD",2))))
        else:
            ws.append(("HiGHS upper bound",solved.bound))
            ws.append(("HiGHS mip gap",solved.gap))
        return ws

    @staticmethod
    def portfolio_sheet(wb,name,p):
        ws=sheet(wb,name,[("Project",1,2,3,4,5,6,7),("Selection",*(int(i in p.ids) for i in range(1,8)))])
        for label,column in (("NPV, млн","D"),("CAPEX, млн","C"),("MCDA","E")):
            ws.append((label,"="+"+".join(f"{c}$2*Projects!{column}{i}" for i,c in enumerate("BCDEFGH",2))))
        for row in (("Budget slack","=Settings!B2-B4"),("Logic checks","Result","Limit"),
                    ("z2+z3","=C2+D2",1),("z4−z1","=E2-B2",0),
                    ("z5−z7","=F2-H2",0),("Violation","=MAX(0,-B6,B8-1,B9,ABS(B10))")):
            ws.append(row)
        return ws

    @staticmethod
    def binary_sheet(wb):
        ws=sheet(wb,"All128",[("Mask",1,2,3,4,5,6,7,"CAPEX","NPV","Score","Feasible","Feasible NPV","Dominated","Frontier","Audit")])
        for mask in range(128):
            r=mask+2
            bits=[f"=MOD(INT($A{r}/2^{i}),2)" for i in range(7)]
            totals=["="+"+".join(f"{c}{r}*Projects!{source}{i}" for i,c in enumerate("BCDEFGH",2)) for source in "CDE"]
            feasible=f"=--AND(I{r}<=Settings!B2,C{r}+D{r}<=1,E{r}<=B{r},F{r}=H{r})"
            dominated=(f'=COUNTIFS($L$2:$L$129,1,$J$2:$J$129,">"&J{r},$K$2:$K$129,">="&K{r})'
                       f'+COUNTIFS($L$2:$L$129,1,$J$2:$J$129,">="&J{r},$K$2:$K$129,">"&K{r})')
            ws.append((mask,*bits,*totals,feasible,f'=IF(L{r}=1,J{r},"")',"="+dominated,
                       f"=--AND(L{r}=1,N{r}=0)"))
        ws["P2"]="Maximum feasible NPV"
        ws["Q2"]="=MAX(M2:M129)"
        ws["P3"]="Feasible portfolios"
        ws["Q3"]="=SUM(L2:L129)"
        ws["P4"]="Nondominated portfolios"
        ws["Q4"]="=SUM(O2:O129)"
        return ws

    def add_analysis(self,wb,pf,pareto,stress,check,op,sc):
        front=sheet(wb,"Pareto",[("Mask from selected IDs","NPV","MCDA","CAPEX","MRT","True frontier flag","Weighted supported")])
        for i,p in enumerate(pareto["frontier"],2):
            mask=sum(2**(j-1) for j in p.ids)
            front.append((mask,*(f"=INDEX(All128!{c}2:{c}129,A{i}+1)" for c in "JKI"),
                          f"=ABS((B{i}-B{i-1})/(C{i}-C{i-1}))" if i>2 else None,
                          f"=INDEX(All128!O2:O129,A{i}+1)",int((p.npv,p.score) in pareto["supported"])))
            for c,v,unit in (("B",p.npv,"млн руб."),("C",p.score,"балл"),("D",p.capex,"млн руб."),("F",1,"bool")):
                check(front,f"{c}{i}",v,unit)
            if i>2:
                check(front,f"E{i}",pareto["mrt"][i-3]["mrt"],"млн руб./балл")
        eps=sheet(wb,"Epsilon",[("ε","Mask","Formula NPV","Formula MCDA","Feasible")])
        for i,e in enumerate(pareto["epsilon"],2):
            mask=sum(2**(int(j)-1) for j in e["ids"].split("+") if j!="∅")
            eps.append((e["epsilon"],mask,f"=INDEX(All128!J2:J129,B{i}+1)",f"=INDEX(All128!K2:K129,B{i}+1)",
                        f"=--AND(D{i}>=A{i},INDEX(All128!L2:L129,B{i}+1)=1)"))
            check(eps,f"C{i}",e["npv"],"млн руб.")
            check(eps,f"E{i}",1,"bool")
        weighted=sheet(wb,"Weighted",[("Alpha","Mask","NPV normalized","Score normalized","Weighted objective")])
        n0,n1,s0,s1=pareto["ranges"]
        for i,e in enumerate(pareto["weighted"],2):
            mask=sum(2**(int(j)-1) for j in e["ids"].split("+") if j!="∅")
            weighted.append((e["alpha"],mask,f"=(INDEX(All128!J2:J129,B{i}+1)-{n0})/{n1-n0 or 1}",
                             f"=(INDEX(All128!K2:K129,B{i}+1)-{s0})/{s1-s0 or 1}",
                             f"=A{i}*C{i}+(1-A{i})*D{i}"))
            check(weighted,f"E{i}",e["weighted_objective"],"ratio")
        ws=sheet(wb,"Stress",[("Scenario","Mask or product","CAPEX / Δc","NPV / carbon margin","Score / waste","Slack / tax","Feasible")])
        for i,key in enumerate(("finance","green"),2):
            p=stress[key]
            mask=sum(2**(j-1) for j in p.ids)
            budget="B3" if key=="finance" else "B2"
            multiplier="*(1-Settings!B4)" if key=="finance" else ""
            condition=f",E{i}>=Settings!B7" if key=="green" else ""
            ws.append((key,mask,f"=INDEX(All128!I2:I129,B{i}+1)",f"=INDEX(All128!J2:J129,B{i}+1){multiplier}",
                       f"=INDEX(All128!K2:K129,B{i}+1)",f"=Settings!{budget}-C{i}",
                       f"=--AND(F{i}>=0,INDEX(All128!L2:L129,B{i}+1)=1{condition})"))
            for col_,v,unit in (("C",p.capex,"млн руб."),("D",p.npv,"млн руб."),("E",p.score,"балл"),("F",p.slack,"млн руб."),("G",1,"bool")):
                if p.status=="OPTIMAL":
                    check(ws,f"{col_}{i}",v,unit)
        ws.append(("Carbon","Product","Δ margin, тыс.","Margin, тыс.","Waste, t","Tax, тыс.","Output, t"))
        for i,(c,row) in enumerate(zip("BCD",stress["carbon_rows"]),5):
            ws.append(("Carbon",row["product"],f"=Settings!B5*Settings!B6*(1/Products!{c}2-1)/1000",
                       f"=Products!{c}3-C{i}",f"=G{i}*(1/Products!{c}2-1)",f"=E{i}*Settings!B5*Settings!B6/1000",row["carbon_output"]))
            for letter,key,unit in (("C","delta_margin","тыс. руб./т"),("D","carbon_margin","тыс. руб./т"),
                                    ("E","carbon_waste","т"),("F","tax_paid","тыс. руб.")):
                check(ws,f"{letter}{i}",row[key],unit)
        ws.append(("Carbon switches",*stress["carbon"].y))
        ws.append(("Carbon profit","=SUMPRODUCT(D5:D7,G5:G7)-B8*Products!B4-C8*Products!C4-D8*Products!D4"))
        check(ws,"B9",stress["carbon"].objective,"тыс. руб.")

    def verify(self,path,checks,logs,numerical,base,run_solver=True,log_name="excel.log"):
        worker=Path(__file__).with_name("office_worker.py")
        log=logs/log_name
        if run_solver:
            try:
                result=subprocess.run([sys.executable,str(worker),"excel",str(path)],capture_output=True,encoding="utf-8",
                                      errors="replace",timeout=100,cwd=logs)
                log.write_text(result.stdout+result.stderr,encoding="utf-8")
                details=json.loads(result.stdout) if result.stdout.strip() else {}
                if result.returncode or set(details.get("statuses",{}))!={"LP","MILP","Fixed LP","Knapsack"}:
                    details["status"]="EXCEL_NOT_VERIFIED"
            except (OSError,subprocess.TimeoutExpired,ValueError) as error:
                log.write_text(str(error),encoding="utf-8")
                details={"status":"EXCEL_NOT_VERIFIED"}
        else:
            details={"status":"EXCEL_NOT_VERIFIED"}
            log.write_text("Excel COM skipped by explicit CLI option.\n",encoding="utf-8")
        wb=load_workbook(path,data_only=True)
        rows=list(numerical)
        try:
            reports=details.get("sensitivity_sheets",[])
            if details["status"]=="PASS" and len(reports)==2:
                for name,key in zip(reports,("lp","fixed")):
                    refs={str(row[1].value):row[4] for row in wb[name].iter_rows(min_col=1,max_col=5)
                          if row[1].value is not None and row[4].data_type=="n" and row[4].value is not None}
                    metrics=[(f"$B${i}",v,"тыс. руб./ед.") for i,v in enumerate(base[key].shadow,5)]
                    metrics.extend((f"${c}$2",v,"тыс. руб./т") for c,v in zip("BCD",base[key].reduced))
                    for addr,value,unit in metrics:
                        c=refs.get(addr)
                        if c is None:
                            raise RuntimeError(f"Excel native sensitivity missing {name}!{addr}")
                        checks.append(dict(check=f"{name}: {addr}",sheet=name,cell=c.coordinate,python_value=float(value),
                                           unit=unit,tolerance=CHECK_TOL,source="Excel Solver Sensitivity Report"))
            for check in checks:
                value=wb[check["sheet"]][check["cell"]].value
                numeric=isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value)
                difference=value-check["python_value"] if numeric else None
                ok= numeric and abs(difference)<=check["tolerance"]
                rows.append(dict(**check,reference_value=value,difference=difference,
                                 status=("PASS" if ok else "FAIL") if details["status"]=="PASS" else "EXCEL_NOT_VERIFIED"))
        finally:
            wb.close()
        if any(row["status"]=="FAIL" for row in rows):
            details["status"]="FAIL"
        return rows,details


def numerical_row(check,actual,reference,unit,source,tolerance=CHECK_TOL):
    diff=actual-reference
    return dict(check=check,python_value=actual,reference_value=reference,difference=diff,unit=unit,
                tolerance=tolerance,source=source,status="PASS" if abs(diff)<=tolerance else "FAIL")
