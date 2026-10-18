"""Executed edge cases, shock scenario, sensitivity and tree figures."""
from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from model import ArbitrageConditionError, ModelResult, ProjectInputData, calculate


def stress_tests(base: ProjectInputData) -> list[dict]:
    rows=[]
    try:
        x=calculate(base.changed(sigma=0.0001))
        rows.append({"test":"sigma=0.0001","status":"PASS","rov":x.rov,"npv_strat":x.npv_strat,"details":f"u={x.params.u:.9g}; d={x.params.d:.9g}; p={x.params.p:.9g}; denominator={x.params.u-x.params.d:.9g}"})
    except ArbitrageConditionError as exc:
        rows.append({"test":"sigma=0.0001","status":"WARNING","rov":None,"npv_strat":None,"details":f"Degenerate CRR violates no-arbitrage: {exc}"})
    x=calculate(base.changed(K=1e9))
    rows.append({"test":"K=1e9","status":"PASS" if abs(x.rov)<1e-8 else "FAIL","rov":x.rov,"npv_strat":x.npv_strat,"details":"Useless expansion option"})
    x=calculate(base,p_override=1)
    rows.append({"test":"p_override=1","status":"PASS" if x.rov>=0 else "FAIL","rov":x.rov,"npv_strat":x.npv_strat,"details":"synthetic probability override; backward induction only"})
    bad=None
    for r in (0.1,0.2,0.4,0.8,1.6):
        for T in (3,6,12):
            candidate=base.changed(r=r,T=T,N=1)
            try:
                calculate(candidate)
            except ArbitrageConditionError as exc:
                bad=(candidate,str(exc));break
        if bad:break
    if bad is None:
        rows.append({"test":"arbitrage violation","status":"FAIL","rov":None,"npv_strat":None,"details":"Search found no violating input"})
    else:
        candidate,detail=bad
        rows.append({"test":"arbitrage violation","status":"PASS","rov":None,"npv_strat":None,"details":f"Controlled exception for r={candidate.r}, T={candidate.T}, N={candidate.N}: {detail}"})
    return rows


def scenario_comparison(base: ModelResult, shock: ModelResult, path: Path) -> list[dict]:
    metrics={"sigma":(base.inputs.sigma,shock.inputs.sigma),"u":(base.params.u,shock.params.u),"d":(base.params.d,shock.params.d),"p":(base.params.p,shock.params.p),"ROV":(base.rov,shock.rov),"NPV_trad":(base.npv_trad,shock.npv_trad),"NPV_strat":(base.npv_strat,shock.npv_strat)}
    rows=[{"metric":key,"base":a,"shock":b,"absolute_change":b-a,"relative_change":(b-a)/abs(a) if a else ""} for key,(a,b) in metrics.items()]
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    return rows


def sensitivity(base: ProjectInputData, path: Path) -> list[dict]:
    rows=[]
    for sigma in (.1,.2,.3,.35,.4,.5,.6,.7,.75,.8):
        try:
            x=calculate(base.changed(sigma=sigma))
            rows.append({"sigma":sigma,"rov":x.rov,"npv_strat":x.npv_strat,"status":"PASS"})
        except ArbitrageConditionError:
            rows.append({"sigma":sigma,"rov":"","npv_strat":"","status":"INVALID_ARBITRAGE"})
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    return rows


def plot_tree(result: ModelResult, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    N=result.inputs.N
    fig,ax=plt.subplots(figsize=(max(9,N*3),max(6,N*2)))
    for i,row in enumerate(result.option):
        for node in row:
            y=2*node.j-i
            if i<N:
                for dj in (0,1):
                    yy=2*(node.j+dj)-(i+1)
                    ax.plot([i,i+1],[y,yy],color="#8ca3b5",lw=1,zorder=1)
            color="#f9c784" if node.decision=="EXERCISE" else "#dceaf6"
            ax.scatter([i],[y],s=4500,c=color,edgecolors="#17365d",zorder=2)
            ax.text(i,y,f"S={node.S:.2f}\nC={node.C:.2f}\n{node.decision}",ha="center",va="center",fontsize=8,zorder=3)
    ax.set_xlim(-.5,N+.5);ax.set_ylim(-N-1,N+1)
    ax.set_xticks(range(N+1));ax.set_yticks([]);ax.set_xlabel("CRR step")
    ax.set_title(f"American expansion option | sigma={result.inputs.sigma:.0%} | USD million")
    for spine in ax.spines.values():spine.set_visible(False)
    fig.tight_layout();fig.savefig(path,dpi=170);plt.close(fig)
