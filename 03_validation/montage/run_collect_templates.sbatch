#!/bin/bash
#SBATCH --job-name=collect_templates
#SBATCH --output=collect_templates.%j.out
#SBATCH --error=collect_templates.%j.err
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G

set -euo pipefail

ROOT="${DB:-/path/to/cast_data}"

# If your cluster requires a module/conda env, load it here.
# module load python

python3 "${ROOT}/collect_templates.py" \
  --root "${ROOT}" \
  --ages "5-18" \
  --sexes "male,female" \
  --mode copy \
  # add --overwrite if you intentionally want to replace existing Templates/ files

