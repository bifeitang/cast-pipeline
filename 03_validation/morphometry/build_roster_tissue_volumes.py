#!/usr/bin/env python3
"""Build the per-subject tissue-volume table for the TEMPLATE CONSTRUCTION rosters.

`tissue_volumes_all.csv` is the quality-screened subject pool binned by each subject's own
age. That is a different set from the per-template construction rosters of Table 1: it holds
1,461 subjects in the 5-18 range against the rosters' 1,272, it contains 366 subjects that
built no template, and it lacks 164 that did. Most importantly it contains NONE of the 52
subjects of the 2026-07 age-11-female rebuild, which is why data-descriptor Fig. 4 could not
respond to that rebuild at all.

This script assembles the roster table instead: one row per construction subject, labelled
with the stratum it actually built rather than with its own age.

Sources
  1. the construction warp list -- the authoritative roster, one warp per contributing
     subject, giving both the subject id and its stratum
  2. `tissue_volumes_all.csv` for the 1,108 subjects already measured
  3. `ROSTER_VOLUMES_2026-07-26/out/volumes.tsv` for the 164 that were not

Both volume sources use the same method: FreeSurfer `aseg.mgz` through `mri_segstats`,
summing identical label sets (see compute_tissue_volumes_inner.sh). They are therefore
method-matched. FSL FAST volumes are NOT interchangeable with these and must not be mixed in.

Usage:
    build_roster_tissue_volumes.py <per_warp_results.tsv> <tissue_volumes_all.csv> \
                                   <roster_volumes.tsv> <out.tsv>
"""
import csv
import re
import sys


def base_id(warp_name):
    """Strip the index the build appends: '<ID><n>' or '<ID>_rc<n>'."""
    if "_rc" in warp_name:
        return warp_name.split("_rc")[0]
    for n in (12, 11):
        if re.match(r"^NDAR[A-Z0-9]{%d}$" % (n - 4), warp_name[:n]):
            return warp_name[:n]
    return warp_name


def main():
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    warps_p, pool_p, new_p, out_p = sys.argv[1:5]

    roster = {}
    with open(warps_p) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            roster.setdefault(base_id(r["subject"]), r["stratum"])
    print("construction roster: %d subjects across %d strata"
          % (len(roster), len(set(roster.values()))))

    vol = {}
    with open(pool_p) as f:
        for r in csv.DictReader(f):
            try:
                vol[r["subject_id"]] = (float(r["wm_ml"]), float(r["gm_ml"]),
                                        float(r["csf_ml"]), float(r["icv_ml"]))
            except (KeyError, ValueError):
                pass
    n_pool = sum(1 for s in roster if s in vol)
    print("  already measured (screened-pool table): %d" % n_pool)

    n_new = 0
    with open(new_p) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            s = r["subject_id"]
            # no roster-membership guard: this file is generated FROM the roster, and its
            # ids are the canonical ones. Requiring `s in roster` would drop subjects whose
            # roster key carries an extra index digit (an 11-char id read as 12).
            if s not in vol:
                vol[s] = (float(r["wm_ml"]), float(r["gm_ml"]),
                          float(r["csf_ml"]), float(r["icv_ml"]))
                n_new += 1
    print("  newly measured this round               : %d" % n_new)

    rows, missing = [], []
    for s, stratum in sorted(roster.items(), key=lambda kv: (kv[1], kv[0])):
        if s not in vol and len(s) == 12 and s[:11] in vol:
            # NDAR ids are 11 OR 12 chars and the build appends a numeric index, so a
            # 12-char prefix can be a real 11-char id plus the first digit of its index
            # Fall back only when the shorter form actually resolves.
            s = s[:11]
        if s not in vol:
            missing.append((s, stratum))
            continue
        m = re.match(r"age(\d+)_(\w+)", stratum)
        wm, gm, csf, icv = vol[s]
        rows.append(dict(subject_id=s, stratum=stratum, age=int(m.group(1)),
                         sex=m.group(2), wm_ml=wm, gm_ml=gm, csf_ml=csf, icv_ml=icv))

    print("  rows written                            : %d" % len(rows))
    if missing:
        print("  STILL MISSING                           : %d" % len(missing))
        for s, st in missing[:10]:
            print("      %s  %s" % (s, st))

    with open(out_p, "w", newline="") as f:
        w = csv.DictWriter(f, delimiter="\t",
                           fieldnames=["subject_id", "stratum", "age", "sex",
                                       "wm_ml", "gm_ml", "csf_ml", "icv_ml"])
        w.writeheader()
        w.writerows(rows)
    print("wrote", out_p)

    per = {}
    for r in rows:
        per.setdefault((r["age"], r["sex"]), []).append(r)
    ns = [len(v) for v in per.values()]
    print("per-stratum n: min %d max %d over %d strata (roster total %d)"
          % (min(ns), max(ns), len(per), sum(ns)))


if __name__ == "__main__":
    main()
