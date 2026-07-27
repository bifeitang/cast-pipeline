"""F5 (FP section 4.5, Mayerich M1): validity vs reliability.
Reliability (image-based: sharpness, contrast, fractal dimension) does not, by itself,
establish that a template represents anatomy -- a template can be 'reliable but wrong'.
We show that across the 16 BRAIN CAST strata (ages 5-12) the structural VALIDITY (gray-white interface
error) is uniformly sub-voxel and is NOT improved by higher image detail: the correlation
with WM fractal dimension is weakly POSITIVE (r=+0.44, p=0.09; Spearman rho=+0.55, p=0.03),
i.e. the more detailed templates are, if anything, marginally less accurate. Earlier versions
of this script asserted the correlation was ~0; it never was (it was r=+0.54, p=0.03 on the
pre-rebuild data). Also: the defensible cross-template reliability advantage (fractal
dimension) exceeds NKI.
Honest about the data we have: NKI gray-white validity was not measured (the held-out
sweep registered subjects to UH templates), so NKI appears on the reliability axis only."""
import json, glob, re, sys, numpy as np
from scipy import stats
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE, NKI
set_style()

# per-stratum validity (gray-white mean error) + FD (reliability/detail)
val={}
for f in glob.glob("sweep_aggregate/heatmaps/*_summary.json"):
    name=f.split("/")[-1].replace("_summary.json",""); val[name]=json.load(open(f))["cortical"]["mean_abs_err_mm"]
tpl={}
for l in open("morphometry/template_morphometry.jsonl"):
    r=json.loads(l); tpl[r["name"]]=r
nki=[json.loads(l) for l in open("morphometry/nki_morphometry.jsonl")]
nki_fd=np.mean([r["fd"] for r in nki])

rows=[]
for name,e in val.items():
    if name in tpl:
        m=re.match(r"age(\d+)_(\w+)",name)
        rows.append(dict(age=int(m.group(1)),sex=m.group(2),val=e,fd=tpl[name]["fd"]))

fig,ax=plt.subplots(1,1,figsize=(4.8,3.8))
# validity (gray-white error) vs reliability (FD); CAST strata + NKI FD band
for sex,c in [("male",MALE),("female",FEMALE)]:
    rs=[d for d in rows if d["sex"]==sex]
    ax.scatter([d["fd"] for d in rs],[d["val"] for d in rs],s=26,color=c,alpha=0.8,edgecolors="none",label=f"CAST {sex}")
ax.axvspan(nki_fd-0.01,nki_fd+0.01,color=NKI,alpha=0.25)
ax.axvline(nki_fd,color=NKI,lw=1.2,ls="--",label=f"NKI FD ({nki_fd:.2f})")
ax.set_xlabel("reliability: WM fractal dimension"); ax.set_ylabel("gray-white validity error (mm)\n(lower = better)")
ax.set_ylim(0.9,1.3); ax.invert_yaxis()
ax.set_title("Validity is uniformly sub-voxel and\nnot improved by higher image detail",fontsize=8.5)
ax.legend(fontsize=6,loc="best")
# Report the ACTUAL association, with its significance, rather than asserting "decoupled".
# The correlation is positive (more WM detail goes with slightly LARGER interface error),
# i.e. the sharper templates are not the more valid ones -- which is the reliable-but-wrong
# point this figure exists to make. It is not zero, and it must not be labelled as zero.
fd=np.array([d["fd"] for d in rows]); vv=np.array([d["val"] for d in rows])
r,p=stats.pearsonr(fd,vv); rho,prho=stats.spearmanr(fd,vv)
ax.text(0.04,0.10,f"r={r:+.2f} (p={p:.2f}), $\\rho$={rho:+.2f} (p={prho:.2f}), n={len(fd)}",
        transform=ax.transAxes,fontsize=6,color="0.3")

fig.tight_layout(); save(fig,"figures_final/F5_validity_reliability")
print(f"validity range {min(vv):.2f}-{max(vv):.2f} mm; NKI FD {nki_fd:.2f}; n={len(fd)} strata")
print(f"FD vs interface error: Pearson r={r:+.3f} p={p:.3f}; Spearman rho={rho:+.3f} p={prho:.3f}")
