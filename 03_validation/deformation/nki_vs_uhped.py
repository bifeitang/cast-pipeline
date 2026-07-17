import csv, re, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
rows=[r for r in csv.DictReader(open("test_set_on_NKI_template_metrics.csv")) if r['norm_type']=='icv']
def parse(r):
    t=r['template']
    if t.startswith("NKI"): fam,ta,ts='NKI',int(re.search(r'age(\d+)',t).group(1)),None
    else:
        m=re.search(r'age(\d+)_(\w+?)_',t); fam,ta,ts='UH',int(m.group(1)),m.group(2)
    r['_fam'],r['_tage'],r['_tsex']=fam,ta,ts
    r['_sage']=int(re.search(r'(\d+)',r['age_dir']).group(1))
    r['_disp']=float(r['mean_disp_mm']); r['_norm']=float(r['norm_mean_disp'])
    return r
rows=[parse(r) for r in rows]
uh=[r for r in rows if r['_fam']=='UH']; nki=[r for r in rows if r['_fam']=='NKI']

# ---- Panel A: representativeness, UH vs NKI cost by subject age (overlap ages 7-11) ----
fig,(axA,axB)=plt.subplots(1,2,figsize=(12.5,5))
ages=sorted(set(r['_sage'] for r in rows))
def by_sage(data,key):
    return [np.mean([r[key] for r in data if r['_sage']==a]) for a in ages]
axA.plot(ages, by_sage(uh,'_disp'),'-o',color='C0',label='UH-Ped (ours)')
axA.plot(ages, by_sage(nki,'_disp'),'-s',color='C3',label='NKI (reference)')
# paired stats over matched ages
import statistics
uh_all=[r['_disp'] for r in uh]; nki_all=[r['_disp'] for r in nki]
axA.set_xlabel("subject age (years)"); axA.set_ylabel("mean displacement (mm)")
axA.set_title(f"Representativeness: UH-Ped vs NKI (clean metric)\nUH median {np.median(uh_all):.2f} mm vs NKI {np.median(nki_all):.2f} mm  (lower=more representative)")
axA.legend(); axA.grid(alpha=0.2)

# ---- Panel B: does the CLEAN UH cost trend with |age-diff|? ----
ad=np.array([abs(r['_sage']-r['_tage']) for r in uh]); disp=np.array([r['_disp'] for r in uh])
axB.scatter(ad+np.random.default_rng(0).normal(0,0.05,len(ad)), disp, s=6, alpha=0.18, color='C0')
xs=sorted(set(ad)); med=[np.median(disp[ad==x]) for x in xs]
axB.plot(xs,med,'-o',color='navy',lw=2.2,label='binned median')
c=np.polyfit(ad,disp,1)
axB.plot(xs,np.polyval(c,xs),'--',color='C3',lw=2,label=f'linear fit (slope {c[0]:+.3f} mm/yr)')
r_=np.corrcoef(ad,disp)[0,1]
axB.set_xlabel("|subject age − template age| (years)"); axB.set_ylabel("mean displacement (mm)")
axB.set_title(f"Clean UH-Ped cost vs age mismatch\ncorr={r_:+.3f}  (still ~flat → real deformation is age-insensitive)")
axB.legend(); axB.grid(alpha=0.2); axB.set_ylim(0, np.percentile(disp,98))
fig.suptitle("Deformation cost with the CLEAN metric (no translation artifact) — UH-Ped vs NKI, and age-mismatch trend",fontsize=11)
fig.tight_layout(rect=[0,0,1,0.95])
fig.savefig("nki_vs_uhped_clean.png",dpi=150); print("wrote nki_vs_uhped_clean.png")
print(f"\nUH-Ped median {np.median(uh_all):.3f} mm | NKI median {np.median(nki_all):.3f} mm")
print(f"clean UH corr(|age-diff|, disp) = {r_:+.3f}, slope {c[0]:+.3f} mm/yr")
# matched vs mismatched within UH
for lo,hi,lab in [(0,0.5,'matched(|d|=0)'),(0.5,2.5,'near(1-2)'),(2.5,9,'far(3+)')]:
    s=(ad>=lo)&(ad<hi); 
    if s.sum(): print(f"  {lab:18s} median {np.median(disp[s]):.3f} mm  n={s.sum()}")
