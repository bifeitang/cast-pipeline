import csv, re, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, UH, FEMALE, MALE
set_style(); D="DeformationAnalysis/"
sex={r["EID"]:r["Sex_Text"] for r in csv.DictReader(open(D+"hbn_subject_info_all.txt"))}
rows=[r for r in csv.DictReader(open(D+"test_set_on_template_metrics_across_ages.csv")) if r["norm_type"]=="icv"]
recs=[]
for r in rows:
    m=re.search(r"age(\d+)_(\w+?)_",r["template"]);
    if not m: continue
    ta,ts=int(m.group(1)),m.group(2); eid=r["subject_id"]; sa=int(re.search(r"(\d+)",r["age_dir"]).group(1))
    if ts!=sex.get(eid): continue                      # matched-sex only
    recs.append((sa,ta,float(r["mean_disp_mm"])))
sas=sorted({a for a,_,_ in recs}); tas=sorted({b for _,b,_ in recs})
M=np.full((len(sas),len(tas)),np.nan)
for i,sa in enumerate(sas):
    for j,ta in enumerate(tas):
        vals=[d for a,b,d in recs if a==sa and b==ta]
        if vals: M[i,j]=np.mean(vals)
fig,(axA,axB)=plt.subplots(1,2,figsize=(7.2,3.3))
im=axA.imshow(M,cmap="viridis",aspect="auto",origin="lower")
axA.set_xticks(range(len(tas))); axA.set_xticklabels(tas); axA.set_yticks(range(len(sas))); axA.set_yticklabels(sas)
axA.set_xlabel("template age (years)"); axA.set_ylabel("subject age (years)")
# mark per-row minimum
for i in range(len(sas)):
    if np.all(np.isnan(M[i])): continue
    j=np.nanargmin(M[i]); axA.add_patch(plt.Rectangle((j-0.5,i-0.5),1,1,fill=False,edgecolor="w",lw=1.5))
fig.colorbar(im,ax=axA,label="deformation cost (mm)",fraction=0.046)
axA.set_title("Age×age cost (matched sex)\nwhite box = per-subject-age minimum"); panel_letter(axA,"a")
# Panel B: cost vs |age-diff|
ad=np.array([abs(a-b) for a,b,_ in recs]); dd=np.array([d for *_ ,d in recs])
xs=sorted(set(ad)); med=[np.median(dd[ad==x]) for x in xs]
axB.scatter(ad+np.random.default_rng(0).normal(0,.06,len(ad)),dd,s=4,alpha=.12,color=UH)
axB.plot(xs,med,"-o",color="0.1",lw=1.6,ms=4,label="binned median")
c=np.polyfit(ad,dd,1); axB.plot(xs,np.polyval(c,xs),"--",color="#D55E00",lw=1.4,label=f"slope {c[0]:+.3f} mm/yr")
axB.set_xlabel("|subject age − template age| (yr)"); axB.set_ylabel("deformation cost (mm)")
axB.set_ylim(0,np.percentile(dd,97)); axB.legend()
axB.set_title(f"Clean SyN cost vs age mismatch\ncorr={np.corrcoef(ad,dd)[0,1]:+.3f} (warp ~flat; see caption)"); panel_letter(axB,"b")
fig.tight_layout(); save(fig,"figures_final/F2_preview_agexage")
print("F2 diag-min check:", [(sas[i], tas[np.nanargmin(M[i])]) for i in range(len(sas)) if not np.all(np.isnan(M[i]))])
