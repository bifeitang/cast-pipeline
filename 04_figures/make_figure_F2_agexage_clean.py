"""FP Figure (clean section 4.2): honest deformation-cost age trend.
Uses the CLEAN displacement metric (test_set_on_template_metrics_with_subject_age.csv,
mean_disp_mm ~3-4 mm) -- NOT the translation-contaminated test_set_dc (~35 mm).
Shows: matched-age UH template has the lowest cost, the effect is real but GENTLE
(slope ~0.1 mm/yr), and the male matched-best 'V' is NOT statistically significant
(committee Self S1). Honest reframe of the validity-vs-reliability point (Mayerich M1)."""
import csv, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy import stats
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, UH, MALE, FEMALE, OKABE
set_style()

CSV="DeformationAnalysis/test_set_on_template_metrics_with_subject_age.csv"
rows=[]
with open(CSV) as f:
    for x in csv.DictReader(f):
        if x["display_dataset"]!="My Template": continue
        try:
            rows.append(dict(age=float(x["Age"]), tage=float(x["template_age"]),
                             d=float(x["template_age"])-float(x["Age"]),
                             cost=float(x["mean_disp_mm"]), sex=x["Sex_Text"].strip().lower()))
        except: pass
print(f"UH (My Template) rows: {len(rows)}")
d=np.array([r["d"] for r in rows]); cost=np.array([r["cost"] for r in rows])
absd=np.abs(d)

fig,axes=plt.subplots(1,3,figsize=(10.5,3.3))

# --- (a) signed Δage: binned median ± IQR, gentle V, matched (Δ=0) lowest ---
ax=axes[0]
bins=np.arange(-6.5,7.5,1)
cen=[]; med=[]; q1=[]; q3=[]
for lo,hi in zip(bins[:-1],bins[1:]):
    m=(d>=lo)&(d<hi)
    if m.sum()>=10:
        cen.append((lo+hi)/2); med.append(np.median(cost[m]))
        q1.append(np.percentile(cost[m],25)); q3.append(np.percentile(cost[m],75))
cen=np.array(cen); med=np.array(med)
ax.fill_between(cen,q1,q3,color=UH,alpha=0.18,lw=0)
ax.plot(cen,med,"-o",color=UH,ms=4)
ax.axvline(0,color="0.5",ls=":",lw=0.9)
i0=np.argmin(np.abs(cen)); ax.annotate("matched",(0,med[i0]),textcoords="offset points",
    xytext=(4,-14),fontsize=7,color="0.3")
ax.set_xlabel("template age − subject age (years)")
ax.set_ylabel("deformation cost (mean displacement, mm)")
ax.set_title("Cost is lowest at the matched age\n(median ± IQR)",fontsize=8.5)
panel_letter(ax,"a")

# --- (b) |Δage| regression: quantify the gentle slope, with 95% CI + p ---
ax=axes[1]
lr=stats.linregress(absd,cost)
xs=np.linspace(0,absd.max(),50)
ax.scatter(absd+np.random.uniform(-0.12,0.12,len(absd)),cost,s=4,color=UH,alpha=0.10,edgecolors="none")
ax.plot(xs,lr.intercept+lr.slope*xs,"-",color="black",lw=1.6)
# binned medians on top
cen2=[]; med2=[]
for k in range(0,7):
    m=(absd>=k-0.5)&(absd<k+0.5)
    if m.sum()>=10: cen2.append(k); med2.append(np.median(cost[m]))
ax.plot(cen2,med2,"D",color=OKABE["orange"],ms=5,label="binned median")
ax.set_xlabel("age mismatch |Δage| (years)")
ax.set_ylabel("deformation cost (mm)")
ax.set_ylim(2.0,8.5)
ax.set_title(f"Effect is real but gentle\nslope={lr.slope:+.3f} mm/yr  p={lr.pvalue:.1e}",fontsize=8.5)
ax.legend(loc="upper left")
panel_letter(ax,"b")

# --- (c) male 'V' significance (Self S1) ---
ax=axes[2]
for sex,c in [("male",MALE),("female",FEMALE)]:
    rs=[r for r in rows if r["sex"]==sex]
    dd=np.array([r["d"] for r in rs]); cc=np.array([r["cost"] for r in rs])
    cen3=[]; med3=[]
    for lo,hi in zip(bins[:-1],bins[1:]):
        m=(dd>=lo)&(dd<hi)
        if m.sum()>=8: cen3.append((lo+hi)/2); med3.append(np.median(cc[m]))
    ax.plot(cen3,med3,"-o",color=c,ms=3.5,label=sex)
# significance of the matched-best V for males: matched vs mismatched
male=[r for r in rows if r["sex"]=="male"]
m_match=[r["cost"] for r in male if abs(r["d"])<0.5]
m_mis=[r["cost"] for r in male if abs(r["d"])>=2]
U,p_mw=stats.mannwhitneyu(m_match,m_mis,alternative="less")
# also slope test within males
md=np.array([abs(r["d"]) for r in male]); mc=np.array([r["cost"] for r in male])
lrm=stats.linregress(md,mc)
ax.axvline(0,color="0.5",ls=":",lw=0.9)
ax.set_xlabel("template age − subject age (years)")
ax.set_ylabel("deformation cost (mm)")
ax.set_title(f"Male 'V' not significant (Self S1)\nmatched vs mismatch p={p_mw:.2f}; slope p={lrm.pvalue:.2f}",fontsize=8.5)
ax.legend(loc="upper center")
panel_letter(ax,"c")

fig.suptitle("Deformation cost (CLEAN metric): matched-age template is best, but the age effect is gentle and the male V is not significant",fontsize=9.5)
fig.tight_layout(rect=[0,0,1,0.94])
save(fig,"figures_final/F2_agexage_clean")

print("\n=== clean §4.2 stats ===")
print(f"matched(|Δ|<0.5) median = {np.median([r['cost'] for r in rows if abs(r['d'])<0.5]):.3f} mm")
print(f"mismatch(|Δ|>=2) median = {np.median([r['cost'] for r in rows if abs(r['d'])>=2]):.3f} mm")
print(f"all: slope={lr.slope:+.4f} mm/yr, r={lr.rvalue:+.3f}, p={lr.pvalue:.2e}")
print(f"male V: matched vs mismatch Mann-Whitney p={p_mw:.3f}; within-male slope p={lrm.pvalue:.3f}")
