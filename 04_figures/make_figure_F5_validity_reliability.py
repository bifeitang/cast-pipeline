"""F5 (FP section 4.5, Mayerich M1): validity vs reliability.
Reliability (image-based: sharpness, contrast, fractal dimension) does not, by itself,
establish that a template represents anatomy -- a template can be 'reliable but wrong'.
We show that across the 15 UH-Ped strata the structural VALIDITY (gray-white interface
error) is uniformly sub-voxel and essentially decoupled from the reliability metrics, and
that the defensible cross-template reliability advantage (fractal dimension) exceeds NKI.
Honest about the data we have: NKI gray-white validity was not measured (the held-out
sweep registered subjects to UH templates), so NKI appears on the reliability axis only."""
import json, glob, re, sys, numpy as np
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

fig,axes=plt.subplots(1,2,figsize=(8.5,3.6))
# (a) validity (gray-white error) vs reliability (FD); UH strata + NKI FD band
ax=axes[0]
for sex,c in [("male",MALE),("female",FEMALE)]:
    rs=[d for d in rows if d["sex"]==sex]
    ax.scatter([d["fd"] for d in rs],[d["val"] for d in rs],s=26,color=c,alpha=0.8,edgecolors="none",label=f"UH {sex}")
ax.axvspan(nki_fd-0.01,nki_fd+0.01,color=NKI,alpha=0.25)
ax.axvline(nki_fd,color=NKI,lw=1.2,ls="--",label=f"NKI FD ({nki_fd:.2f})")
ax.set_xlabel("reliability: WM fractal dimension"); ax.set_ylabel("gray-white validity error (mm)\n(lower = better)")
ax.set_ylim(0.9,1.3); ax.invert_yaxis()
ax.set_title("Validity is uniformly high,\ndecoupled from image metrics",fontsize=8.5)
ax.legend(fontsize=6,loc="best"); panel_letter(ax,"a")
# annotate decoupling: corr
fd=np.array([d["fd"] for d in rows]); vv=np.array([d["val"] for d in rows])
ax.text(0.04,0.06,f"r(FD,error)={np.corrcoef(fd,vv)[0,1]:+.2f}",transform=ax.transAxes,fontsize=6,color="0.3")

# (b) the two-axis conceptual summary: where each metric lives
ax=axes[1]; ax.axis("off")
ax.text(0.5,1.02,"Validity vs reliability (Mayerich M1)",ha="center",fontsize=9,fontweight="bold",transform=ax.transAxes)
txt=[
 (r"$\bf{Reliability}$ (image-based, necessary not sufficient):",0.92,"0.0"),
 (r"  $\bullet$ edge sharpness — not comparable across",0.83,"0.25"),
 (r"     intensity-normalization conventions",0.76,"0.25"),
 (r"  $\bullet$ GM--WM contrast — comparable (NKI $\gtrsim$ UH)",0.69,"0.25"),
 (r"  $\bullet$ fractal dimension — UH 2.31 $>$ NKI 2.24",0.62,"0.25"),
 (r"  $\bullet$ deformation cost — UH $\approx$ NKI (3.8 vs 3.6 mm)",0.55,"0.25"),
 (r"$\bf{Validity}$ (downstream structural bias — what matters):",0.42,"0.0"),
 (r"  $\bullet$ gray--white interface error: $\bf{1.10\ mm}$ sub-voxel",0.33,"0.0"),
 (r"  $\bullet$ uniform across all 15 strata (1.05--1.18 mm)",0.26,"0.25"),
 (r"  $\bullet$ matched-sex benefit (females, $p<10^{-16}$)",0.19,"0.25"),
 (r"$\Rightarrow$ A template's value is low bias, not high sharpness.",0.06,"0.0"),
]
for s,y,c in txt: ax.text(0.0,y,s,fontsize=7,color=c,transform=ax.transAxes,va="center")
panel_letter(ax,"b")

fig.suptitle("Reliability $\\neq$ validity: image-quality metrics do not establish representativeness; the gray-white bias does",fontsize=8.8)
fig.tight_layout(rect=[0,0,1,0.93]); save(fig,"figures_final/F5_validity_reliability")
print(f"validity range {min(vv):.2f}-{max(vv):.2f} mm; FD-error corr {np.corrcoef(fd,vv)[0,1]:+.2f}; NKI FD {nki_fd:.2f}")
