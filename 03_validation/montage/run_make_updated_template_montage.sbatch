#!/bin/bash
#SBATCH --job-name=updated_template_montage
#SBATCH --output=updated_template_montage.%j.out
#SBATCH --error=updated_template_montage.%j.err
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

set -euo pipefail

ROOT="${DB:-/path/to/cast_data}"
TEMPLATES_DIR="${ROOT}/Templates/UpdatedTemplates"
OUT_PREFIX="${TEMPLATES_DIR}/updated_templates_montage"

# If your cluster requires a module/conda env, load it here.
# module load python

# Minimal dependency fix for clusters where nibabel is installed but typing_extensions is missing.
# Safe + fast (installs to $HOME/.local if needed).
python3 -m pip install --user --upgrade --quiet typing_extensions || true

python3 "${ROOT}/make_template_montage.py" \
  --root "${ROOT}" \
  --templates-dir "${TEMPLATES_DIR}" \
  --out-prefix "${OUT_PREFIX}" \
  --sexes "male,female" \
  --slice-fracs "0.50,0.50,0.50" \
  --dpi 250

