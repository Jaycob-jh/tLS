#!/usr/bin/env bash
set -euo pipefail

# =========================================================================
# RULES / CONTRACT (ENGLISH)
# 1) Submits one sbatch job per PSD SFILE extracted from BLOCK.
# 2) BLOCK can be either:
#      - plain list: one path per line (comments with # allowed), OR
#      - quoted list: paths wrapped in single quotes '...'
# 3) Automatically sets FOOOF_TAG based on BLOCK filename containing "pre" or "post".
# 4) Exports only required variables: BST_CODE, BST_DB, BST_PROTOCOL, SFILE, FOOOF_TAG
# =========================================================================

###you need to change this txt file.(pre/post)
BLOCK="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step2_FOOOF/sfiles_post_net_fooof_list.txt"

export BST_CODE="/ibmgpfs/cuizaixu_lab/jiahai/packages/brainstorm3"
export BST_DB="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/dataset/brainstorm_db"
export BST_PROTOCOL="1064@FP2_rtLS-EEG"

JOB_SCRIPT="/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/code/step2_FOOOF/run_fooof_single.sh"

[[ -x "$JOB_SCRIPT" ]] || { echo "Not found/exec: $JOB_SCRIPT"; exit 2; }
[[ -s "$BLOCK" ]] || { echo "Empty block file: $BLOCK"; exit 2; }

# Decide tag from BLOCK filename
base="$(basename "$BLOCK")"
stage="fooof"
if [[ "$base" == *post* ]]; then stage="post"; fi
if [[ "$base" == *pre*  ]]; then stage="pre";  fi
FOOOF_TAG="${stage}-net-FOOOF"

# Extract SFILEs robustly:
# - If a line contains single-quoted substrings, emit each quoted token.
# - Else treat the whole trimmed line as a path.
extract_sfiles() {
  awk '
    function trim(s){ sub(/^[ \t\r\n]+/,"",s); sub(/[ \t\r\n]+$/,"",s); return s }
    {
      line=$0
      sub(/#.*/,"",line)               # strip comments
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
