from .analysis import ids


def prepare_brief(op,pf,sc,base,pareto,stress,edges,reconciliation,excel,test_count):
    lp=base["lp"]; milp=base["milp"]; exact=base["exact"]; greedy=base["greedy"]
    frontier=pareto["frontier"]
    knee=next((r for r in pareto["knee"] if r.get("knee_status")=="KNEE"),None)
    unsupported=[p for p in frontier if (p.npv,p.score) not in pareto["supported"]]
    skipped=[p for p in frontier if (p.npv,p.score) not in pareto["epsilon_points"]]
    stress_finance=stress["finance"]
    stress_green=stress["green"]
    eligible=[p for p in pareto["feasible"] if p.score>=sc.score_floor]
    return dict(op=op,pf=pf,sc=sc,base=base,pareto=pareto,stress=stress,edges=edges,excel=excel,
                gross=[x/p.yield_rate for x,p in zip(milp.x,op.products)],
                finance_removed=tuple(sorted(set(exact.ids)-set(stress_finance.ids))),
                finance_shock_loss=stress_finance.npv*sc.npv_cut/(1-sc.npv_cut) if sc.npv_cut<1 else 0,
                lp_premium=lp.objective-milp.objective,greedy_loss=exact.npv-greedy.npv,
                knee=knee,unsupported=unsupported,skipped=skipped, finance_loss=exact.npv-stress_finance.npv,
                finance_budget_loss=exact.npv-(stress_finance.npv/(1-sc.npv_cut) if sc.npv_cut<1 else 0),
                green_score_gain=stress_green.score-exact.score if eligible else None,green_options=len(eligible),
                carbon_tax=sum(r["tax_paid"] for r in stress["carbon_rows"]),
                extra_p2=[row[1]*(1/op.products[1].yield_rate-1) for row in op.machine_coefficients],
                observed_tests=test_count,
                excel_checks=sum(row["source"].startswith(("Excel","worksheet")) and row["status"]=="PASS" for row in reconciliation),
                numeric_checks=sum(not row["source"].startswith(("Excel","worksheet")) and row["status"]=="PASS" for row in reconciliation))
