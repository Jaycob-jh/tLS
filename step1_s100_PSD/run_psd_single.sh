#!/bin/bash
#SBATCH -p q_fat
#SBATCH -c 6
#SBATCH -J netpsd
#SBATCH -o ./log/psd_single.%j.out
#SBATCH -e ./log/psd_single.%j.err

# =========================================================================
# RULES / CONTRACT (ENGLISH)
# 1) Runs ONE PSD job for ONE SFILE in Brainstorm (headless).
# 2) Expects SFILE and BST_* variables via sbatch --export.
# 3) HOME and MATLAB_PREFDIR are redirected to GPFS for cluster stability.
# =========================================================================

set -euo pipefail

module load MATLAB/R2019a
mkdir -p ./log

export MATLAB_PREFDIR="/GPFS/cuizaixu_lab_permanent/jiahai/.matlab/R2019a"
export HOME="/GPFS/cuizaixu_lab_permanent/jiahai"
mkdir -p "$MATLAB_PREFDIR"

MATLAB_SCRIPT="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step1_s100_PSD/run_psd_single.m"
[[ -f "$MATLAB_SCRIPT" ]] || { echo "MATLAB script not found: $MATLAB_SCRIPT"; exit 2; }

matlab -batch "ver; exit" >/dev/null 2>&1 || { echo "MATLAB not runnable"; exit 2; }

matlab -batch "run('$MATLAB_SCRIPT');"
