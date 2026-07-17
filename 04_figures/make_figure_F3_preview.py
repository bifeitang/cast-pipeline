import csv, re, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import wilcoxon
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE
set_style(); D="DeformationAnalysis/"
sex={r["EID"]:r["Sex_Text"] for r in csv.DictReader(open(D+"hbn_subject_info_all.txt"))}
rows=[r for r in csv.DictReader(open(D+"test_set_on_updated_templates_metrics.csv")) if r["norm_type"]=="icv"]
# (eid, template_age) -> {female:disp, male:disp}
cell={}
for r in rows:
    m=re.search(r"age(\d+)_(\w+?)_",r["template"]);
    if not m: continue
    ta,ts=int(m.group(1)),m.group(2); eid=r["subject_id"]
    cell.setdefault((eid,ta),{})[ts]=float(r["mean_disp_mm"])
matched=[]; mismatched=[]; ssex=[]
for (eid,ta),v in cell.items():
    s=sex.get(eid);
    if s not in v or ("male" if s=="female" else "female") not in v: continue
    o="male" if s=="female" else "female"
    matched.append(v[s]); mismatched.append(v[o]); ssex.append(s)
matched=np.array(matched); mismatched=np.array(mismatched); ssex=np.array(ssex)
W,p=wilcoxon(matched,mismatched); dz=(mismatched-matched).mean()/(mismatched-matched).std(ddof=1)
fig,ax=plt.subplots(figsize=(4.2,3.4))
rng=np.random.default_rng(0)
for i in range(len(matched)):
    ax.plot([0,1],[matched[i],mismatched[i]],"-",color="0.8",lw=0.4,alpha=0.5,zorder=1)
for x,arr,lab in [(0,matched,"matched sex"),(1,mismatched,"opposite sex")]:
    ax.scatter(np.full(len(arr),x)+rng.normal(0,0.03,len(arr)),arr,s=9,alpha=0.5,
               color=[FEMALE if s=="female" else MALE for s in ssex],zorder=2)
    ax.scatter([x],[np.median(arr)],marker="_",s=600,color="k",zorder=3,lw=2)
ax.set_xticks([0,1]); ax.set_xticklabels(["matched\nsex","opposite\nsex"]); ax.set_ylabel("deformation cost (mm)")
ax.set_title(f"Gender-specificity (ages 5/10/15, n={len(matched)})\nΔmed={np.median(mismatched-matched):+.3f} mm, "
             f"Wilcoxon p={p:.1e}, dz={dz:.2f}")
fig.tight_layout(); save(fig,"figures_final/F3_preview_sex")
print(f"matched median {np.median(matched):.3f}  mismatched {np.median(mismatched):.3f}  p={p:.2e}  n={len(matched)}")
