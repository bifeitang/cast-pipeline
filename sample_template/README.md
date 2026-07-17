# Demo template (single stratum)

This folder holds **one** CAST template as an illustrative sample so the repository is
runnable/inspectable without the full data deposit:

- `age9_male_template.nii.gz` — age-9 male group-average T1w template
- `age9_male_brain_mask.nii.gz` — its brain mask

## The full library is in the data deposit, not here

The complete **28-template** library (ages 5–18 × {male, female}) plus brain masks and
tissue-probability maps is distributed through the dedicated template **data deposit**
(OpenNeuro / Zenodo), not this code repository (see Hard Rule: code-only repo).

> **Data DOI:** `[PENDING — to be minted]`

The comparator templates used in the head-to-head validation (NKI = Dong 2020; Fonov/NIHPD)
are redistributed from their original sources under their own licenses — see the methods paper.

Templates are NIfTI in native template space; the demo above corresponds to the age-9 male
panel shown in the manuscript's template-comparison figure.
