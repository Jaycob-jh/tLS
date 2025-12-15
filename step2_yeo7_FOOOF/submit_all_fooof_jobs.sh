#!/usr/bin/env bash
set -euo pipefail

# =========================================================================
# RULES / CONTRACT (ENGLISH)
# 1) Submits one sbatch job per PSD SFILE extracted from BLOCK.
# 2) BLOCK can be either:
#      - plain list: one path per line (# comments allowed), OR
#      - quoted list: paths wrapped in single quotes '...'
# 3) Automatically sets FOOOF_TAG based on BLOCK filename containing "pre" or "post".
# 4) Exports only required variables: BST_CODE, BST_DB, BST_PROTOCOL, SFILE, FOOOF_TAG
# =========================================================================

BLOCK="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step2_FOOOF/sfiles_post_net_fooof_list.txt"

export BST_CODE="/ibmgpfs/cuizaixu_lab/jiahai/packages/brainstorm3"
export BST_DB="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/dataset/brainstorm_db"
export BST_PROTOCOL="1064@FP2_rtLS-EEG"

# NOTE: update this path to your yeo7 job script if different
JOB_SCRIPT="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step2_FOOOF/run_fooof_single.sh"

[[ -x "$JOB_SCRIPT" ]] || { echo "Not found/exec: $JOB_SCRIPT"; exit 2; }
[[ -s "$BLOCK" ]] || { echo "Empty block file: $BLOCK"; exit 2; }

base="$(basename "$BLOCK")"
stage="post"
[[ "$base" == *pre*  ]] && stage="pre"
[[ "$base" == *post* ]] && stage="post"

FOOOF_TAG="${stage}-yeo7-FOOOF"

extract_sfiles() {
  awk '
    function trim(s){ sub(/^[ \t\r\n]+/,"",s); sub(/[ \t\r\n]+$/,"",s); return s }
    {
      line=$0
      sub(/#.*/,"",line)
      line=trim(line)
      if (line=="") next

      if (index(line, "'\''")>0) {
        n=split(line, a, "'\''")
        for (i=2; i<=n; i+=2) {
          s=trim(a[i])
          if (s!="") print s
        }
      } else {
        print line
      }
    }
  ' "$BLOCK"
}

extract_sfiles | while IFS= read -r SFILE; do
  [[ -z "$SFILE" ]] && continue
  sbatch --export=BST_CODE,BST_DB,BST_PROTOCOL,SFILE="$SFILE",FOOOF_TAG="$FOOOF_TAG" "$JOB_SCRIPT"
done
