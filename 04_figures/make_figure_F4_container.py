#!/usr/bin/env python3
"""Fig. 4 -- one environment across three stages, and how to run the released code.

Replaces `container_workflow.tex`, a TikZ card layout that carried the whole argument
in prose. Same content, but the flow is drawn and the prose is reduced to what a reader
needs in order to reproduce a run: the entry point of each stage.

Panel b is a row-per-directory list rather than a card grid. Side-by-side cards cannot
hold a 30-character command at a legible size once the figure is scaled to the 131 mm
text block (see figs_schematic.TYPE_SCALE), and truncating the entry points would defeat
the point of showing them.

Provenance -- nothing here is unsourced:
  base image, tool versions ..... cast-pipeline/container/Dockerfile
                                  (Ubuntu 22.04; FSL 6.0.7 L33, AFNI 23.2.04 L39,
                                  ANTs 2.5.0 L46, FreeSurfer 7.4.1 L57,
                                  MRIQC 0.16.1 + DeepBET L66-69)
  image name, digest policy,
  the two build variants ........ cast-pipeline/container/README.md
  directory roles, entry points . cast-pipeline/README.md "Layout" and the per-directory
                                  READMEs; the preprocessing entry point is the
                                  scheduler, which itself issues
                                  `sbatch process_subject_s1.sh …` (L17)
  SLURM stages, binds ........... manuscript Sec. "Reproducibility and computing
                                  environment"

Run:  python3 make_figure_F4_container.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_schematic as S                                        # noqa: E402
from figs_style import set_style                                  # noqa: E402

ROOT = "/path/to/cast-project"
OUT = f"{os.path.dirname(os.path.abspath(__file__))}/F4_container"

W, H = 180.0, 112.0
STAGE_Y, STAGE_H, STAGE_W = 70.0, 34.0, 50.0
STAGE_X = [3.0, 65.0, 127.0]

STAGES = [
    ("1  DOCKER · BUILD", 0,
     ["Ubuntu 22.04 base image",
      "ANTs 2.5.0 · FreeSurfer 7.4.1",
      "FSL 6.0.7 · AFNI 23.2.04",
      "CAT12 12.9 · MRIQC 0.16.1",
      "DeepBET brain masking"],
     "docker build container/"),
    ("2  DOCKER HUB · PUBLISH", 1,
     ["published once, then pulled",
      "by immutable sha256 digest,",
      "never a moving tag — so the",
      "environment cannot drift",
      "between debugging and production"],
     "docker push mri_template_env"),
    ("3  APPTAINER · HPC RUN", 3,
     ["unprivileged .sif — Docker",
      "needs root, not permitted here",
      "SLURM arrays over subjects",
      "and age × sex strata",
      "binds /project and scratch"],
     "apptainer build … docker://…"),
]

# (directory, hue, role, entry-point command)
REPO = [("01_preprocessing/", 0, "ten steps of Fig. 1, one job per subject",
         "bash batch_job_scheduler_s1.sh"),
        ("02_template_construction/", 0, "ANTs groupwise build + the 30 as-run scripts",
         "mri_template_construction.sh <age> <sex>"),
        ("03_validation/", 2, "symmetric ASSD, fractal dimension, cost",
         "python3 verify_assd.py   verify_fd.py"),
        ("04_figures/", 2, "one generator per figure in both papers",
         "python3 make_figure_*.py")]

NAME_X, ROLE_X, CMD_X = 7.0, 50.0, 108.0


def row(ax, y, name, hue, role, cmd, h=6.8):
    col = S.ACCENT
    S.rbox(ax, 3.0, y - h / 2, 174.0, h, fc="white", ec=S.tint(col, .35))
    S.rbox(ax, 3.0, y - h / 2, 1.8, h, fc=col, ec="none", r=0.5, z=3)
    S.txt(ax, NAME_X, y, name, fs=5.6, weight="bold", family="monospace",
          color=col, va="center")
    S.txt(ax, ROLE_X, y, role, fs=5.7, color=S.MUTE, va="center")
    S.code(ax, CMD_X, y, cmd, fs=5.2)


def main():
    set_style()
    fig, ax = S.canvas(W, H)

    # ================================================== panel a: the environment
    S.panel_label(ax, 2.0, 111.0, "a")
    S.txt(ax, 8.0, 107.6, "One image definition, three stages — nothing recompiled "
                          "between development and production", fs=7.0, weight="bold")

    for (title, hue, lines, cmd), x in zip(STAGES, STAGE_X):
        col = S.ACCENT       # uni-color: one accent across Figs 1, 2 and 4
        S.rbox(ax, x, STAGE_Y, STAGE_W, STAGE_H, fc="white", ec=S.tint(col, .40))
        S.band(ax, x, STAGE_Y + STAGE_H - 5.0, STAGE_W, 5.0, col, title, fs=6.2)
        for i, s in enumerate(lines):
            S.txt(ax, x + 3.2, STAGE_Y + STAGE_H - 9.8 - i * 3.8, s, fs=5.7,
                  color=S.INK if i == 0 else S.MUTE)
        S.code(ax, x + 2.6, STAGE_Y + 4.4, cmd, fs=5.2)

    # No arrow labels: each card already carries the command that makes the hop.
    for i in range(2):
        y = STAGE_Y + STAGE_H / 2
        S.arrow(ax, STAGE_X[i] + STAGE_W + 1.4, y, STAGE_X[i + 1] - 1.4, y,
                lw=1.1, head=3.0, color=S.ACCENT)

    S.rbox(ax, 3.0, 58.4, 174.0, 9.0, fc="#FAFBFC", ec=S.RULE)
    S.txt(ax, 6.0, 64.2, "Two builds", fs=5.9, weight="bold")
    S.txt(ax, 6.0, 60.6, "are released", fs=5.9, weight="bold")
    S.txt(ax, 30.0, 64.2, "as-run — SANLM by CAT12 under MATLAB, the exact environment "
                          "that produced the templates;", fs=5.7, color=S.MUTE)
    S.txt(ax, 30.0, 60.6, "license-free — SANLM by ANTs DenoiseImage, the same Manjón "
                          "2010 algorithm, so nothing proprietary is required.",
          fs=5.7, color=S.MUTE)

    # =================================================== panel b: repo and usage
    S.panel_label(ax, 2.0, 54.0, "b")
    S.txt(ax, 8.0, 50.6, "Released code — what each directory does and how it is run",
          fs=7.0, weight="bold")

    for i, (name, hue, role, cmd) in enumerate(REPO):
        y = 44.0 - i * 7.8
        row(ax, y, name, hue, role, cmd)
        if i:
            S.arrow(ax, 5.4, y + 7.8 - 3.4, 5.4, y + 3.6, lw=0.8, head=2.0,
                    color=S.tint(S.ACCENT, .55))

    # setup, which is not a pipeline stage
    S.rbox(ax, 3.0, 1.5, 174.0, 12.0, fc="#FAFBFC", ec=S.RULE)
    S.txt(ax, NAME_X, 9.6, "container/", fs=5.6, weight="bold", family="monospace",
          va="center")
    S.txt(ax, ROLE_X, 9.6, "Dockerfile — every stage above runs inside it",
          fs=5.7, color=S.MUTE, va="center")
    S.code(ax, CMD_X, 9.6, "docker build -t cast-pipeline:1.0.0 container/", fs=4.8)
    S.txt(ax, NAME_X, 5.0, "config.sh", fs=5.6, weight="bold", family="monospace",
          va="center")
    S.txt(ax, ROLE_X, 5.0, "all paths as overridable variables — ships non-functional "
                           "placeholders, so edit it first",
          fs=5.7, color=S.MUTE, va="center")

    S.save(fig, OUT)


if __name__ == "__main__":
    main()
