"""DD-F6 / M-F1: templates encode development.
Overlay each template's tissue volumes (FAST, from template_morphometry.jsonl) on the
subject-derived developmental norms (FreeSurfer, tissue_volumes_summary_by_age_sex.csv,
n=1473). Template GM/WM track the subject growth curves and the WM/GM ratio rises with
age (myelination) -- i.e. the templates are developmentally faithful, not generic.
Caption notes the FAST-vs-FreeSurfer segmentation comparison (GM matches closely; CSF
differs by definition, so we show GM, WM, and the scale-free WM/GM ratio)."""
import json, re, sys, csv, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE
set_style()

# --- template morphometry (FAST) ---
tpl=[json.loads(l) for l in open("morphometry/template_morphometry.jsonl") if l.strip()]
for r in tpl:
    m=re.match(r"age(\d+)_(\w+)",r["name"]); r["age"]=int(m.group(1)); r["sex"]=m.group(2)
def tser(sex,k):
    rs=sorted([r for r in tpl if r["sex"]==sex],key=lambda r:r["age"])
    return np.array([r["age"] for r in rs]), np.array([r[k] for r in rs])

# --- subject developmental norms (FreeSurfer) ---
norm={}
with open("morphometry/tissue_volumes_summary_by_age_sex.csv") as f:
    for x in csv.DictReader(f):
        try:
            n=int(x["n_subjects"])
            if n<5: continue   # drop thin bins (e.g. age11 female n=1)
            norm.setdefault(x["sex"],[]).append(dict(age=float(x["age"]), n=n,
                wm=float(x["wm_ml_mean"]), wmsd=float(x["wm_ml_std"] or 0),
                gm=float(x["gm_ml_mean"]), gmsd=float(x["gm_ml_std"] or 0)))
        except Exception:
            pass
for s in norm: norm[s]=sorted(norm[s],key=lambda d:d["age"])

fig,axes=plt.subplots(1,3,figsize=(10.5,3.4))
def band(ax,sex,key,sdkey,c):
    d=norm[sex]; a=np.array([x["age"] for x in d]); m=np.array([x[key] for x in d]); sd=np.array([x[sdkey] for x in d])
    ax.fill_between(a,m-sd,m+sd,color=c,alpha=0.13,lw=0)
    ax.plot(a,m,"-",color=c,lw=1.1,alpha=0.7)

# (a) WM
ax=axes[0]
for sex,c in [("male",MALE),("female",FEMALE)]:
    band(ax,sex,"wm","wmsd",c); a,v=tser(sex,"wm_ml"); ax.plot(a,v,"o",color=c,ms=4,label=f"{sex} template")
ax.set_xlabel("age (years)"); ax.set_ylabel("white-matter volume (mL)")
cc=np.corrcoef([r["age"] for r in tpl],[r["wm_ml"] for r in tpl])[0,1]
ax.set_title(f"WM grows with age (template r={cc:+.2f})",fontsize=8.5); panel_letter(ax,"a"); ax.legend(fontsize=6)

# (b) GM
ax=axes[1]
for sex,c in [("male",MALE),("female",FEMALE)]:
    band(ax,sex,"gm","gmsd",c); a,v=tser(sex,"gm_ml"); ax.plot(a,v,"o",color=c,ms=4)
ax.set_xlabel("age (years)"); ax.set_ylabel("gray-matter volume (mL)")
cc=np.corrcoef([r["age"] for r in tpl],[r["gm_ml"] for r in tpl])[0,1]
ax.set_title(f"GM plateaus/declines (template r={cc:+.2f})",fontsize=8.5); panel_letter(ax,"b")

# (c) WM/GM ratio (scale-free myelination index)
ax=axes[2]
for sex,c in [("male",MALE),("female",FEMALE)]:
    d=norm[sex]; a=np.array([x["age"] for x in d]); ratio=np.array([x["wm"]/x["gm"] for x in d])
    ax.plot(a,ratio,"-",color=c,lw=1.1,alpha=0.6)
    at,wt=tser(sex,"wm_ml"); _,gt=tser(sex,"gm_ml"); ax.plot(at,wt/gt,"o",color=c,ms=4)
allr=np.array([r["wm_ml"]/r["gm_ml"] for r in tpl]); cc=np.corrcoef([r["age"] for r in tpl],allr)[0,1]
ax.set_xlabel("age (years)"); ax.set_ylabel("WM / GM volume ratio")
ax.set_title(f"Myelination index rises (template r={cc:+.2f})",fontsize=8.5); panel_letter(ax,"c")

fig.suptitle("Templates encode development: FAST tissue volumes (points) track the subject growth norms (bands, FreeSurfer mean$\\pm$SD)",fontsize=9.5)
fig.tight_layout(rect=[0,0,1,0.94]); save(fig,"figures_final/M1_developmental_norms")

print("=== DD-F6 trends (template morphometry) ===")
for k in ["wm_ml","gm_ml","icv_ml"]:
    a=np.array([r["age"] for r in tpl]); v=np.array([r[k] for r in tpl])
    print(f"  template {k}: age r={np.corrcoef(a,v)[0,1]:+.2f}")
print("  template WM/GM ratio: age r=%.2f"%np.corrcoef([r['age'] for r in tpl],allr)[0,1])
