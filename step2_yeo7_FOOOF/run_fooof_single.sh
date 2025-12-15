#!/bin/bash
#SBATCH -p q_fat_c
#SBATCH -c 6
#SBATCH -J fooof
#SBATCH -o ./log/fooof_single.%j.out
#SBATCH -e ./log/fooof_single.%j.err

# =========================================================================
# RULES / CONTRACT (ENGLISH)
# 1) Runs ONE FOOOF job for ONE PSD SFILE in Brainstorm (headless).
# 2) Expects SFILE, BST_CODE, BST_DB, BST_PROTOCOL (and optional FOOOF_TAG)
#    to be passed via sbatch --export.
# 3) HOME and MATLAB_PREFDIR are redirected to GPFS for cluster stability.
# =========================================================================

set -euo pipefail

module load MATLAB/R2019a
mkdir -p ./log

export MATLAB_PREFDIR="/GPFS/cuizaixu_lab_permanent/jiahai/.matlab/R2019a"
export HOME="/GPFS/cuizaixu_lab_permanent/jiahai"
mkdir -p "$MATLAB_PREFDIR"

# NOTE: update this path to your yeo7 FOOOF folder if different
MATLAB_SCRIPT="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step2_FOOOF/run_fooof_single.m"
[[ -f "$MATLAB_SCRIPT" ]] || { echo "MATLAB script not found: $MATLAB_SCRIPT"; exit 2; }

matlab -batch "ver; exit" >/dev/null 2>&1 || { echo "MATLAB not runnable"; exit 2; }

matlab -batch "run('$MATLAB_SCRIPT');"
