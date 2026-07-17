import json, re, numpy as np
from scipy import stats
MORPH = "/path/to/cast-project/07_Results_and_Analysis/morphometry"
cast = [json.loads(l) for l in open(MORPH+"/template_morphometry.jsonl") if l.strip()]
nki  = [json.loads(l) for l in open(MORPH+"/nki_morphometry.jsonl") if l.strip()]
def page(n): return int(re.search(r"age[-_]?0*(\d+)", n, re.I).group(1))
def psex(n):
    nl=n.lower()
    if "female" in nl or re.search(r"sex-?f|_f(?:[_\-.]|$)", nl): return "female"
    if "male"   in nl or re.search(r"sex-?m|_m(?:[_\-.]|$)", nl): return "male"
    return "?"
for r in cast: r["age"],r["sex"]=page(r["name"]),psex(r["name"])
for r in nki:  r["age"]=page(r["name"])
print("=== CAST templates ===")
for r in sorted(cast,key=lambda x:(x["age"],x["sex"])):
    print(f'  {r["name"]:26s} age={r["age"]:2d} {r["sex"]:6s} fd={r.get("fd")} vox={r.get("vox_mm")}')
print(f"  n_cast={len(cast)}")
cba={}; 
for r in cast: cba.setdefault(r["age"],[]).append(r)
nba={r["age"]:r for r in nki}
overlap=sorted(set(cba)&set(nba))
print("overlap ages:",overlap)
def paired(c,n,label):
    c=np.array(c,float); n=np.array(n,float); d=c-n
    if len(d)<2: print(f"[{label}] n={len(d)}"); return
    t,pt=stats.ttest_rel(c,n)
    try: W,pw=stats.wilcoxon(c,n)
    except Exception: W,pw=float('nan'),float('nan')
    dz=d.mean()/d.std(ddof=1); se=d.std(ddof=1)/np.sqrt(len(d))
    ci=d.mean()+np.array([-1,1])*stats.t.ppf(.975,len(d)-1)*se
    print(f"[{label}] n={len(d)} meanD={d.mean():+.4f} pos={int((d>0).sum())}/{len(d)} t={t:.2f} p_t={pt:.2e} Wilcox_p={pw:.2e} dz={dz:.2f} CI=[{ci[0]:+.4f},{ci[1]:+.4f}]")
print("\n--- PRIMARY: sex-averaged CAST vs NKI, all overlap ages ---")
print(f'{"age":>4}{"CAST":>8}{"NKI":>8}{"D":>8}  NKImask')
ca=[];na=[]
for a in overlap:
    cfd=np.mean([r["fd"] for r in cba[a]]); nfd=nba[a]["fd"]; ca.append(cfd); na.append(nfd)
    print(f'{a:>4}{cfd:>8.3f}{nfd:>8.3f}{cfd-nfd:>+8.3f}  {nba[a].get("had_mask")}')
paired(ca,na,"all-ages sex-avg (=D4 +0.072?)")
am=[a for a in overlap if nba[a].get("had_mask") is True]
print("\n--- MASKED-ONLY (NKI had_mask=True; ages",am,") ---")
paired([np.mean([r["fd"] for r in cba[a]]) for a in am],[nba[a]["fd"] for a in am],"masked-only sex-avg (CLEANEST headline)")
print("\n--- RESOLUTION-MATCHED: CAST 1.0mm vs NKI 1.0mm ---")
rm=[(r,nba[r["age"]]) for r in cast if abs(r.get("vox_mm",0)-1.0)<1e-6 and r["age"] in nba]
for c,n in sorted(rm,key=lambda x:(x[0]["age"],x[0]["sex"])):
    print(f'  age{c["age"]:2d} {c["sex"]:6s} CAST={c["fd"]:.3f} NKI={n["fd"]:.3f} D={c["fd"]-n["fd"]:+.3f} NKImask={n.get("had_mask")}')
paired([c["fd"] for c,n in rm],[n["fd"] for c,n in rm],"res-matched 1.0mm (=D4 +0.033?)")
rmm=[(c,n) for c,n in rm if n.get("had_mask") is True]
paired([c["fd"] for c,n in rmm],[n["fd"] for c,n in rmm],"res-matched + NKI-masked (STRICTEST)")
print("\n--- FD vs age / vox ---")
r,p=stats.pearsonr([r["age"] for r in cast],[r["fd"] for r in cast]); print(f"CAST FD~age r={r:+.3f} p={p:.2e} n={len(cast)}")
r,p=stats.pearsonr([r["age"] for r in nki],[r["fd"] for r in nki]);  print(f"NKI  FD~age r={r:+.3f} p={p:.2e} n={len(nki)}")
r,p=stats.pearsonr([r["vox_mm"] for r in cast],[r["fd"] for r in cast]); print(f"CAST FD~vox r={r:+.3f} p={p:.2e}")
f08=[r["fd"] for r in cast if abs(r["vox_mm"]-0.8)<1e-6]; f10=[r["fd"] for r in cast if abs(r["vox_mm"]-1.0)<1e-6]
tt,pp=stats.ttest_ind(f08,f10,equal_var=False); print(f"  0.8mm mean={np.mean(f08):.3f}(n={len(f08)}) vs 1.0mm mean={np.mean(f10):.3f}(n={len(f10)}) Welch t={tt:.2f} p={pp:.3f}")
