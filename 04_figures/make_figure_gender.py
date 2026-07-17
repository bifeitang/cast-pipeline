import json, re, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0,"/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE
set_style()
rows=[json.loads(l) for l in open("morphometry/template_morphometry.jsonl") if l.strip()]
for r in rows:
    m=re.match(r"age(\d+)_(\w+)",r["name"]); r["age"]=int(m.group(1)); r["sex"]=m.group(2)
def series(sex,k):
    rs=sorted([r for r in rows if r["sex"]==sex],key=lambda r:r["age"])
    return np.array([r["age"] for r in rs]), np.array([r[k] for r in rs])

fig,axes=plt.subplots(1,3,figsize=(9.5,3.2))
for ax,(k,lab,L) in zip(axes,[("icv_ml","ICV (mL)","a"),("wm_ml","WM volume (mL)","b"),("gm_ml","GM volume (mL)","c")]):
    for sex,c in [("male",MALE),("female",FEMALE)]:
        a,v=series(sex,k); ax.plot(a,v,"-o",color=c,ms=4,label=sex)
    # % male > female across matched ages
    am,vm=series("male",k); af,vf=series("female",k)
    common=sorted(set(am)&set(af)); dm=[vm[list(am).index(x)] for x in common]; df=[vf[list(af).index(x)] for x in common]
    pct=100*np.mean((np.array(dm)-np.array(df))/np.array(df))
    ax.set_xlabel("template age (years)"); ax.set_ylabel(lab); panel_letter(ax,L)
    ax.set_title(f"{lab.split(' ')[0]}: males {pct:+.0f}% vs females",fontsize=9)
    if L=="a": ax.legend()
fig.suptitle("Gender-specificity (a–c): templates capture sex dimorphism (males larger at every age)",fontsize=10)
fig.tight_layout(rect=[0,0,1,0.95]); save(fig,"figures_final/Gender_dimorphism")
# numbers
for k in ["icv_ml","wm_ml","gm_ml"]:
    am,vm=series("male",k); af,vf=series("female",k); common=sorted(set(am)&set(af))
    dm=np.array([vm[list(am).index(x)] for x in common]); df=np.array([vf[list(af).index(x)] for x in common])
    print(f"{k}: male>female in {100*np.mean(dm>df):.0f}% of ages, mean +{100*np.mean((dm-df)/df):.1f}%")
