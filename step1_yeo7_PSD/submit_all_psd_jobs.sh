#!/usr/bin/env bash
set -euo pipefail

# =========================================================================
# RULES / CONTRACT (ENGLISH)
# 1) Submits one sbatch job per non-empty, non-comment line in LIST.
# 2) Each line must be a valid Brainstorm sFile reference (e.g., link|...).
# 3) Exports environment to job via --export=ALL (kept to match original behavior).
# =========================================================================

LIST="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step1_s100_PSD/sfiles_PSD_list.txt"

export BST_CODE="/ibmgpfs/cuizaixu_lab/jiahai/packages/brainstorm3"
export BST_DB="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/dataset/brainstorm_db"
export BST_PROTOCOL="1064@FP2_rtLS-EEG"

JOB_SCRIPT="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step1_yeo7_PSD/run_psd_single.sh"
[[ -x "$JOB_SCRIPT" ]] || { echo "Not found/exec: $JOB_SCRIPT"; exit 2; }

while IFS= read -r SFILE || [[ -n "${SFILE:-}" ]]; do
  [[ -z "$SFILE" || "$SFILE" =~ ^[[:space:]]*# ]] && continue
  export SFILE
  sbatch --export=ALL "$JOB_SCRIPT"
done < "$LIST"
