#!/usr/bin/env python3
"""Refresh the Jacobian columns of the clean deformation CSV from the test_set_dc tree.

WHY ONLY THE JACOBIAN COLUMNS
-----------------------------
`test_set_on_template_metrics_with_subject_age.csv` is the CLEAN table: its
`mean_disp_mm` has the near-rigid coordinate-origin offset removed (~3-4 mm), whereas the
raw `test_set_dc` metrics carry it (~35 mm). `make_figure_F2_agexage_clean.py` depends on
that clean displacement and says so in its own docstring. Rebuilding the whole table from
test_set_dc would therefore silently re-contaminate the manuscript's age-by-age figure.

The Jacobian columns are a different story. A pure translation has unit Jacobian
everywhere, so `mean_logJ`, `std_logJ` and `pct_non_diffeomorphic` are unaffected by the
offset and can be taken from test_set_dc directly. Those three are exactly what the data
descriptor's Fig. 8 panel c consumes, and nothing else in the figure set reads them from
this file.

WHY ALL TEN TEMPLATES, NOT JUST AGE-11-FEMALE
---------------------------------------------
The table's Jacobians were computed in 2025-11 and their source metrics.txt files no
longer exist -- the 2026-01 run overwrote those paths in place. Across 1,088 pairs where
both generations survive, `std_logJ` differs by a median of 4.8% and a 95th percentile of
37%, so the two conventions cannot be mixed: dropping a new age-11-female column into an
old table would confound "rebuilt template" with "different pipeline". Refreshing all ten
templates at once puts panel c back on a single convention.

Usage:
    update_jacobians_from_test_set_dc.py <test_set_dc_merged.csv> <target.csv> [--dry-run]

The merged CSV is produced on carya by
DeformationCost/merge_test_set_dc_metrics.py and must carry subject_id, template,
mean_logJ, std_logJ and pct_non_diffeomorphic.
"""
import csv
import shutil
import sys

JAC_COLS = ("mean_logJ", "std_logJ", "pct_non_diffeomorphic")
TEMPLATES = {f"age{a}_{s}_template.nii.gz" for a in (7, 8, 9, 10, 11)
             for s in ("female", "male")}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) < 2:
        raise SystemExit(__doc__)
    src_path, tgt_path = args[0], args[1]

    src = {}
    with open(src_path) as f:
        for r in csv.DictReader(f):
            t = r.get("template")
            if t in TEMPLATES and all(r.get(c) not in (None, "") for c in JAC_COLS):
                src[(r["subject_id"], t)] = r
    print("new Jacobians available: %d rows across %d templates"
          % (len(src), len({t for _, t in src})))
    missing = TEMPLATES - {t for _, t in src}
    if missing:
        print("WARNING: no new values for %s" % ", ".join(sorted(missing)))

    with open(tgt_path) as f:
        rdr = csv.DictReader(f)
        fields = rdr.fieldnames
        rows = list(rdr)

    updated = untouched = absent = 0
    deltas = []
    for r in rows:
        if r.get("display_dataset") != "My Template" or r.get("template") not in TEMPLATES:
            untouched += 1
            continue
        new = src.get((r["subject_id"], r["template"]))
        if new is None:
            # Cannot be refreshed -- these subjects' source images no longer exist in the
            # test set, so the run cannot be repeated. Blank the three Jacobian columns
            # rather than leave 2025-11 values sitting beside refreshed ones: panel c
            # skips non-numeric std_logJ, so it stays single-convention, while the
            # displacement columns are untouched and make_figure_F2_agexage_clean.py keeps
            # its full row set.
            for c in JAC_COLS:
                r[c] = ""
            absent += 1
            continue
        try:
            deltas.append(abs(float(new["std_logJ"]) - float(r["std_logJ"])))
        except (TypeError, ValueError):
            pass
        for c in JAC_COLS:
            r[c] = new[c]
        updated += 1

    print("rows updated: %d | left alone: %d | no new value: %d" % (updated, untouched, absent))
    if deltas:
        deltas.sort()
        print("std_logJ change: median %.5f  mean %.5f  p95 %.5f  max %.5f"
              % (deltas[len(deltas) // 2], sum(deltas) / len(deltas),
                 deltas[int(0.95 * len(deltas))], deltas[-1]))
    if absent:
        print("NOTE: %d rows had no new value; their Jacobian columns were BLANKED so panel c "
              "excludes them and stays single-convention. Their displacement columns are "
              "untouched." % absent)

    if dry:
        print("\n--dry-run: nothing written")
        return
    shutil.copy2(tgt_path, tgt_path + ".bak_pre_jacobian_refresh")
    with open(tgt_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("wrote %s (backup: .bak_pre_jacobian_refresh)" % tgt_path)
    print("displacement columns were NOT touched -- they remain the clean metric that "
          "make_figure_F2_agexage_clean.py depends on.")


if __name__ == "__main__":
    main()
