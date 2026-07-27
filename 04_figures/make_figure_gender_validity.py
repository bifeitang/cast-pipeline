"""Gender validity panel: the cross-sex gray-white penalty (the structural half of the
sex-specificity thesis). Per held-out subject, affine-align to the matched-sex template
and to the opposite-sex template; compare cortical gray-white error.
KEY (honest) FINDING: the matched-sex benefit is sex-asymmetric -- significant for FEMALE
subjects (matched female template fits female cortex better, +0.05 mm, p<1e-16) but absent
for males. Reported transparently."""
import json, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy import stats
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE
set_style()
rows=[json.loads(l) for l in open("sweep_aggregate/sweep_measures.jsonl") if l.strip()]
ma={}; xa={}
for r in rows:
    if r["kind"]=="matched_affine": ma[r["subject_id"]]=r
    elif r["kind"]=="cross_affine": xa[r["subject_id"]]=r
P=[(e, ma[e]["cort_mean_mm"], xa[e]["cort_mean_mm"], ma[e]["template_sex"]) for e in ma if e in xa]
m=np.array([p[1] for p in P]); x=np.array([p[2] for p in P]); sexes=[p[3] for p in P]

fig,axes=plt.subplots(1,2,figsize=(7.2,3.4))
# (a) paired scatter matched vs cross, colored by subject sex
ax=axes[0]
for sx,c in [("female",FEMALE),("male",MALE)]:
    mm=np.array([p[1] for p in P if p[3]==sx]); xx=np.array([p[2] for p in P if p[3]==sx])
    ax.scatter(mm,xx,s=10,color=c,alpha=0.5,edgecolors="none",label=f"{sx} (n={len(mm)})")
# limits from the data (with a small margin) rather than a fixed [1.0,2.2] box, which
# left ~60% of the panel empty and squashed the points against the diagonal.
lo=min(m.min(),x.min()); hi=max(m.max(),x.max()); pad=0.05*(hi-lo)
lim=[lo-pad,hi+pad]; ax.plot(lim,lim,"--",color="0.4",lw=1); ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
ax.set_xlabel("matched-sex template error (mm)"); ax.set_ylabel("opposite-sex template error (mm)")
ax.set_title("Above diagonal = matched-sex better",fontsize=8.5); ax.legend(fontsize=6,loc="upper left"); panel_letter(ax,"a")

# (b) penalty (cross - matched) by subject sex, with stats
ax=axes[1]
data=[]; labs=[]; cols=[]; stats_txt=[]
for sx,c in [("female",FEMALE),("male",MALE)]:
    d=np.array([p[2]-p[1] for p in P if p[3]==sx]); data.append(d); labs.append(f"{sx}\n(n={len(d)})"); cols.append(c)
    # TWO-SIDED: the male effect is a reversal, so the one-sided "greater" test used
    # previously reported p=1 for it, which reads as "no effect" when it is in fact a
    # highly significant effect in the opposite direction.
    W,p=stats.wilcoxon(d)
    stats_txt.append(f"{np.mean(d):+.3f} mm, p={p:.0e}\n{int((d>0).sum())}/{len(d)} favour matched")
bp=ax.boxplot(data,tick_labels=labs,patch_artist=True,widths=0.5,showfliers=False)
for patch,c in zip(bp["boxes"],cols): patch.set_facecolor(c); patch.set_alpha(0.5)
ax.axhline(0,color="0.4",ls=":",lw=1)
# headroom so the annotation clears the upper whisker cap instead of printing across it
y0,y1=ax.get_ylim(); ax.set_ylim(y0,y1+0.42*(y1-y0))
for i,t in enumerate(stats_txt):
    ax.text(i+1,ax.get_ylim()[1],t,ha="center",va="top",fontsize=6)
ax.set_ylabel("cross-sex penalty (mm)\n(opposite − matched)")
ax.set_title("Penalty is female-specific (honest)",fontsize=8.5); panel_letter(ax,"b")

# "no penalty for males" was wrong: males show a significant REVERSAL (p=2e-28), not a
# null. The honest statement is that the matched-sex benefit is female-specific.
fig.suptitle("Cross-sex gray-white penalty: the matched-sex benefit is female-specific; males fit the female template better",fontsize=8.8)
fig.tight_layout(rect=[0,0,1,0.93]); save(fig,"figures_final/Gender_crosssex_validity")

print("=== cross-sex penalty (affine, cortical mean) ===")
print(f"n paired={len(P)}; overall penalty {np.mean(x-m):+.3f} mm, Wilcoxon p={stats.wilcoxon(x,m)[1]:.2e}")
for sx in ["female","male"]:
    d=np.array([p[2]-p[1] for p in P if p[3]==sx]); W,p=stats.wilcoxon(d)
    print(f"  {sx} (n={len(d)}): {np.mean(d):+.3f} mm, p={p:.2e}, dz={np.mean(d)/np.std(d):+.2f}, "
          f"{int((d>0).sum())}/{len(d)} favour matched")

# Numbers quoted in the manuscript caption, printed here so the caption is checkable.
# 'The female template is an easier target for everyone': error to the FEMALE template
# vs error to the MALE template, pooled over all subjects regardless of their own sex.
ef=[];em=[]
for e,mm,xx,sx in P:
    if sx=="female": ef.append(mm); em.append(xx)
    else: em.append(mm); ef.append(xx)
d=np.array(em)-np.array(ef)
print(f"  female template easier for everyone (n={len(d)}): {d.mean():+.3f} mm, p={stats.wilcoxon(d)[1]:.1e}")
df=np.array([p[2]-p[1] for p in P if p[3]=="female"]); dm=np.array([p[2]-p[1] for p in P if p[3]=="male"])
print(f"  interaction (penalty_female - penalty_male) = {df.mean()-dm.mean():+.3f} mm")
