import csv, re, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import wilcoxon
sys.path.insert(0,".."); sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, UH, NKI, panel_letter
set_style()
D="DeformationAnalysis/"
sex={r["EID"]:r["Sex_Text"] for r in csv.DictReader(open(D+"hbn_subject_info_all.txt"))}
rows=[r for r in csv.DictReader(open(D+"test_set_on_NKI_template_metrics.csv")) if r["norm_type"]=="icv"]
def info(r):
    t=r["template"]
    if t.startswith("NKI"): fam,ta,ts="NKI",int(re.search(r"age(\d+)",t).group(1)),None
    else: m=re.search(r"age(\d+)_(\w+?)_",t); fam,ta,ts="UH",int(m.group(1)),m.group(2)
    return fam,ta,ts
# index: (eid, template_age) -> {UH: disp, NKI: disp}, UH at subject's matched sex
cell={}
for r in rows:
    fam,ta,ts=info(r); eid=r["subject_id"]; sa=int(re.search(r"(\d+)",r["age_dir"]).group(1))
    d=float(r["mean_disp_mm"])
    if fam=="UH" and ts!=sex.get(eid): continue   # UH: matched-sex only
    cell.setdefault((eid,ta),{})["sa"]=sa; cell[(eid,ta)][fam]=d
# matched-age paired set: template_age == subject age, both UH & NKI present (overlap 7-11)
pairs=[(v["UH"],v["NKI"],v["sa"]) for (eid,ta),v in cell.items()
       if "UH" in v and "NKI" in v and ta==v["sa"]]
uh=np.array([p[0] for p in pairs]); nk=np.array([p[1] for p in pairs]); ages=np.array([p[2] for p in pairs])
W,p=wilcoxon(uh,nk); med_d=np.median(uh-nk)

fig,(axA,axB)=plt.subplots(1,2,figsize=(7.0,3.2))
# Panel A: cost vs subject age, UH vs NKI (matched-age), mean+95%CI
agelist=sorted(set(ages))
def msci(arr,a):
    x=arr[ages==a]; m=x.mean(); se=x.std(ddof=1)/np.sqrt(len(x)); return m,1.96*se
for arr,c,lab in [(uh,UH,"UH-Ped (ours)"),(nk,NKI,"NKI (reference)")]:
    ms=[msci(arr,a) for a in agelist]; m=[z[0] for z in ms]; ci=[z[1] for z in ms]
    axA.errorbar(agelist,m,yerr=ci,fmt="-o",color=c,ms=3,capsize=2,lw=1.4,label=lab)
axA.set_xlabel("subject age (years)"); axA.set_ylabel("deformation cost (mm)")
axA.set_title("Representativeness vs reference\n(matched-age template)"); axA.legend()
panel_letter(axA,"a")
# Panel B: paired per-subject UH vs NKI
axB.scatter(nk,uh,s=8,alpha=0.4,color=UH,edgecolors="none")
lim=[0,max(uh.max(),nk.max())*1.05]; axB.plot(lim,lim,"--",color="0.4",lw=1)
axB.set_xlim(lim); axB.set_ylim(lim); axB.set_aspect("equal")
axB.set_xlabel("NKI cost (mm)"); axB.set_ylabel("UH-Ped cost (mm)")
frac=100*np.mean(uh<nk)
axB.set_title(f"Paired (n={len(pairs)})\nUH lower in {frac:.0f}% of subjects\nΔmed={med_d:+.2f} mm, Wilcoxon p={p:.1e}")
panel_letter(axB,"b")
fig.tight_layout()
save(fig,"figures_final/F4_uhped_vs_nki")
print(f"UH median {np.median(uh):.2f}  NKI median {np.median(nk):.2f}  n_pairs={len(pairs)}  p={p:.2e}")
