import json, sys, re, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE
set_style()
rows=[json.loads(l) for l in open("morphometry/template_morphometry.jsonl") if l.strip()]
for r in rows:
    m=re.match(r"age(\d+)_(\w+)",r["name"]); r["age"]=int(m.group(1)); r["sex"]=m.group(2)
    r["weber"]=(r["meanWM"]-r["meanGM"])/r["meanGM"]
def sub(sex): return sorted([r for r in rows if r["sex"]==sex], key=lambda r:r["age"])
def arr(rs,k): return np.array([r["age"] for r in rs]), np.array([r[k] for r in rs])

fig,axes=plt.subplots(2,2,figsize=(7.2,6.0))
metrics=[("edge_strength","gray–white edge sharpness (∇/mm)","a"),
         ("weber","GM–WM contrast (Weber)","b"),
         ("fd","fractal dimension (WM surface)","c"),
         ("wm_ml","WM volume (mL)","d")]
for ax,(k,lab,L) in zip(axes.ravel(),metrics):
    for sex,c in [("female",FEMALE),("male",MALE)]:
        rs=sub(sex); a,v=arr(rs,k)
        # marker by resolution
        res=np.array([r["vox_mm"] for r in rs])
        for mk,rmask in [("o",res<0.9),("s",res>=0.9)]:
            if rmask.any(): ax.scatter(a[rmask],v[rmask],marker=mk,s=28,color=c,alpha=0.85,
                                       edgecolors="none",label=f"{sex} {'0.8mm' if mk=='o' else '1.0mm'}")
        ax.plot(a,v,"-",color=c,lw=1,alpha=0.5)
        # ring age9
        for r in rs:
            if r["age"]==9: ax.scatter([9],[r[k]],s=90,facecolor="none",edgecolor="red",lw=1.4,zorder=5)
    if k!="wm_ml":
        allv=[r[k] for r in rows]; cc=np.corrcoef([r["age"] for r in rows],allv)[0,1]
        ax.set_title(f"{lab}\nage corr={cc:+.2f}",fontsize=8)
    else:
        # add GM too
        for sex,c in [("female",FEMALE),("male",MALE)]:
            rs=sub(sex); a,v=arr(rs,"gm_ml"); ax.plot(a,v,"--",color=c,lw=1,alpha=0.6)
        ax.set_title(f"{lab} (solid) + GM (dashed)",fontsize=8)
    ax.set_xlabel("template age (years)"); ax.set_ylabel(lab,fontsize=7); panel_letter(ax,L)
axes[0,0].legend(fontsize=5.5,ncol=2,loc="best")
fig.suptitle("Template distinctiveness — generic vs age/sex-specific?  (red ring = age-9)",fontsize=10)
fig.tight_layout(rect=[0,0,1,0.96]); save(fig,"figures_final/M2_distinctiveness")

# verdict numbers
print("=== distinctiveness verdict ===")
for k in ["edge_strength","gmwm_contrast","fd","wm_ml","gm_ml","icv_ml"]:
    ages=np.array([r["age"] for r in rows]); v=np.array([r[k] for r in rows])
    print(f"  {k}: age-corr {np.corrcoef(ages,v)[0,1]:+.2f}  range [{v.min():.2f},{v.max():.2f}]")
# M vs F
for k in ["wm_ml","gm_ml","icv_ml","gmwm_contrast"]:
    mf=[r[k] for r in rows if r["sex"]=="male"]; ff=[r[k] for r in rows if r["sex"]=="female"]
    print(f"  {k}: male mean {np.mean(mf):.1f} vs female {np.mean(ff):.1f}")
# age9 z vs neighbors (age7-11 same sex)
print("=== age9 outlier check (z vs age7-11 same sex) ===")
for sex in ["female","male"]:
    nb=[r for r in rows if r["sex"]==sex and r["age"] in (7,8,10,11)]
    for k in ["edge_strength","gmwm_contrast","fd","vox_mm"]:
        nbv=np.array([r[k] for r in nb]); a9=[r[k] for r in rows if r["sex"]==sex and r["age"]==9]
        if a9 and nbv.std()>0: print(f"  {sex} {k}: age9={a9[0]:.3f}  neighbors {nbv.mean():.3f}±{nbv.std():.3f}  z={(a9[0]-nbv.mean())/nbv.std():+.2f}")
