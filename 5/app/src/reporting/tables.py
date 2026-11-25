from ..repositories import write_csv
from ..services.analysis import ids,portfolio_row


class ResultTables:
    def __init__(self,path):
        self.path=path

    def put(self,name,rows,columns=None):
        write_csv(self.path/(name+".csv"),rows,columns)

    def base(self,op,pf,base):
        resource_labels=("Агрегат 1","Агрегат 2","Агрегат 3","NMP","Наномодификатор")
        units=("маш.-ч","маш.-ч","маш.-ч","л","кг")
        effective=[]
        for r,unit,row in zip(resource_labels,units,op.machine_coefficients+op.material_coefficients):
            for p,a in zip(op.products,row):
                effective.append(dict(resource=r,resource_unit=unit,product=p.code,raw=a,effective=a/p.yield_rate,
                                      extra=a*(1/p.yield_rate-1)))
        self.put("effective",effective)
        self.put("products",[dict(product=p.code,name=p.name,yield_rate=p.yield_rate,margin=p.margin) for p in op.products])
        self.put("projects",[dict(id=p.id,name=p.name,capex=p.capex,npv=p.npv,score=p.score) for p in pf.projects])
        operations=[]; resources=[]; production=[]; rc=[]
        for case,r in (("LP",base["lp"]),("MILP",base["milp"]),("Fixed LP",base["fixed"])):
            operations.append(dict(case=case,status=r.status,profit=r.objective,x1=r.x[0],x2=r.x[1],x3=r.x[2],
                                   y1=r.y[0],y2=r.y[1],y3=r.y[2],upper_bound=r.bound,mip_gap=r.gap))
            for i,(name,unit,resource) in enumerate(zip(resource_labels,units,op.machines+op.materials)):
                price=float(r.shadow[i]) if r.shadow else None
                resources.append(dict(case=case,resource=name,unit=unit,physical_capacity=resource.capacity,
                                      rhs=r.rhs[i],load=r.load[i],slack=r.slack[i],shadow=price,
                                      binding=abs(r.slack[i])<1e-6,utilization=r.load[i]/resource.capacity if resource.capacity else None,
                                      shadow_x_slack=price*r.slack[i] if price is not None else None))
            for i,p in enumerate(op.products):
                production.append(dict(case=case,product=p.code,good=r.x[i],gross=r.x[i]/p.yield_rate,
                                       waste=r.x[i]*(1/p.yield_rate-1)))
                if r.reduced:
                    rc.append(dict(case=case,variable=p.code,reduced_cost=float(r.reduced[i]),level=r.x[i],
                                   complementarity=float(r.reduced[i]*r.x[i]),upper_bound_shadow=None,
                                   upper_complementarity=None))
                if r.launch_reduced:
                    rc.append(dict(case=case,variable=f"y{i+1}",reduced_cost=float(r.launch_reduced[i]),level=r.y[i],
                                   complementarity=float(r.launch_reduced[i]*r.y[i]),upper_bound_shadow=float(r.upper_shadow[i]),
                                   upper_complementarity=float(r.upper_shadow[i]*(1-r.y[i]))))
        self.put("operations",operations)
        self.put("resources",resources)
        self.put("production",production)
        self.put("reduced_costs",rc)
        self.put("portfolio_pi",[dict(id=p.id,capex=p.capex,npv=p.npv,score=p.score,pi=1+p.npv/p.capex) for p in pf.projects])
        self.put("greedy_steps",base["greedy_attempts"])
        self.put("portfolio_comparison",[portfolio_row(base[key],method=label)
                 for key,label in (("greedy","Жадный PI"),("exact","MILP"),("enumeration","Перебор"),("control","Контроль"))])

    def analysis(self,pareto,stress,base,edges,sc):
        self.put("edge_cases",edges)
        self.put("pareto_all_feasible",[portfolio_row(p) for p in pareto["feasible"]])
        self.put("pareto_nondominated",[portfolio_row(p,epsilon_found=(p.npv,p.score) in pareto["epsilon_points"],
                   weighted_supported=(p.npv,p.score) in pareto["supported"]) for p in pareto["frontier"]])
        self.put("epsilon_solutions",pareto["epsilon"])
        self.put("weighted_solutions",pareto["weighted"])
        self.put("normalization",[dict(npv_min=pareto["ranges"][0],npv_max=pareto["ranges"][1],
                                        score_min=pareto["ranges"][2],score_max=pareto["ranges"][3])])
        self.put("mrt",pareto["mrt"], ("from_ids","to_ids","from_score","to_score","from_npv","to_npv",
                                       "score_gain","npv_loss","mrt","efficient"))
        self.put("knee",pareto["knee"])
        self.put("stress_operations",stress["carbon_rows"])
        self.put("stress_profit",[dict(case=case,profit=r.objective,profit_delta=r.objective-base["milp"].objective,
                     x1=r.x[0],x2=r.x[1],x3=r.x[2],upper_bound=r.bound,gap=r.gap)
                     for case,r in (("База",base["milp"]),("Налог CO₂",stress["carbon"]))])
        exact=base["exact"]
        rows=[]
        for case,result,budget in (("База",exact,exact.capex+exact.slack),("Секвестр",stress["finance"],sc.stress_budget),
                                   ("Порог MCDA",stress["green"],exact.capex+exact.slack)):
            rows.append(portfolio_row(result,case=case,budget=budget,delta_npv=result.npv-exact.npv,
                        delta_score=result.score-exact.score,removed="+".join(map(str,sorted(set(exact.ids)-set(result.ids)))) or "∅",
                        added="+".join(map(str,sorted(set(result.ids)-set(exact.ids)))) or "∅",
                        corequisite_active=5 in result.ids and 7 in result.ids))
        self.put("stress_portfolio",rows)
