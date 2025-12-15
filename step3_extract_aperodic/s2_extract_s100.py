#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Summarize FOOOF (Schaefer100 resolution) into long-format tables.

Inputs
  - /GPFS/.../results/FOOOF/sub*/ *pre-s100*.csv and *post-s100*.csv

Outputs
  - /GPFS/.../results/offset_s100.csv
  - /GPFS/.../results/exponent_s100.csv

Output columns
  - Subject
  - Day
  - Condition
      1 = same-day pre
      3 = same-day post
      4 = next-day pre (still attributed to the previous day)
  - MeasureID (channel name)
  - Value

Day rule
  - Day is taken from the t-number in the filename (e.g., t1 -> Day=1, t3 -> Day=3).
"""

import os, re, glob
import pandas as pd
from collections import defaultdict

# ---------- Paths ----------
ROOT_FOOOF = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/FOOOF"
OUT_DIR    = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results"
PATTERNS   = [
    os.path.join(ROOT_FOOOF, "sub*", "*pre-s100*.csv"),
    os.path.join(ROOT_FOOOF, "sub*", "*post-s100*.csv"),
]
OUT_OFFSET = os.path.join(OUT_DIR, "offset_s100.csv")
OUT_EXP    = os.path.join(OUT_DIR, "exponent_s100.csv")

# ---------- Fixed measure order (based on your S100 list; FP2 is excluded) ----------
S100_ORDER = [
    "Cont_Cing_1 L","Cont_Cing_1 R","Cont_Par_1 L","Cont_Par_1 R","Cont_Par_2 R",
    "Cont_pCun_1 L","Cont_pCun_1 R","Cont_PFCl_1 L","Cont_PFCl_1 R","Cont_PFCl_2 R",
    "Cont_PFCl_3 R","Cont_PFCl_4 R","Cont_PFCmp_1 R",
    "Default_Par_1 L","Default_Par_1 R","Default_Par_2 L",
    "Default_pCunPCC_1 L","Default_pCunPCC_1 R","Default_pCunPCC_2 L","Default_pCunPCC_2 R",
    "Default_PFC_1 L","Default_PFC_2 L","Default_PFC_3 L","Default_PFC_4 L","Default_PFC_5 L",
    "Default_PFC_6 L","Default_PFC_7 L","Default_PFCdPFCm_1 R","Default_PFCdPFCm_2 R",
    "Default_PFCdPFCm_3 R","Default_PFCv_1 R","Default_PFCv_2 R",
    "Default_Temp_1 L","Default_Temp_1 R","Default_Temp_2 L","Default_Temp_2 R","Default_Temp_3 R",
    "DorsAttn_FEF_1 L","DorsAttn_FEF_1 R","DorsAttn_Post_1 L","DorsAttn_Post_1 R","DorsAttn_Post_2 L",
    "DorsAttn_Post_2 R","DorsAttn_Post_3 L","DorsAttn_Post_3 R","DorsAttn_Post_4 L","DorsAttn_Post_4 R",
    "DorsAttn_Post_5 L","DorsAttn_Post_5 R","DorsAttn_Post_6 L","DorsAttn_PrCv_1 L","DorsAttn_PrCv_1 R",
    "Limbic_OFC_1 L","Limbic_OFC_1 R","Limbic_TempPole_1 L","Limbic_TempPole_1 R","Limbic_TempPole_2 L",
    "SalVentAttn_FrOperIns_1 L","SalVentAttn_FrOperIns_1 R","SalVentAttn_FrOperIns_2 L",
    "SalVentAttn_Med_1 L","SalVentAttn_Med_1 R","SalVentAttn_Med_2 L","SalVentAttn_Med_2 R",
    "SalVentAttn_Med_3 L","SalVentAttn_ParOper_1 L","SalVentAttn_PFCl_1 L",
    "SalVentAttn_TempOccPar_1 R","SalVentAttn_TempOccPar_2 R",
    "SomMot_1 L","SomMot_1 R","SomMot_2 L","SomMot_2 R","SomMot_3 L","SomMot_3 R",
    "SomMot_4 L","SomMot_4 R","SomMot_5 L","SomMot_5 R","SomMot_6 L","SomMot_6 R",
    "SomMot_7 R","SomMot_8 R",
    "Vis_1 L","Vis_1 R","Vis_2 L","Vis_2 R","Vis_3 L","Vis_3 R","Vis_4 L","Vis_4 R",
    "Vis_5 L","Vis_5 R","Vis_6 L","Vis_6 R","Vis_7 L","Vis_7 R","Vis_8 L","Vis_8 R","Vis_9 L",
]
MEAS_RANK = {m:i for i,m in enumerate(S100_ORDER)}
COND_RANK = {1:0, 3:1, 4:2}  # 1=same-day pre, 3=same-day post, 4=next-day pre mapped to previous day

# ---------- Utilities ----------
def parse_filename(path: str):
    """
    Parse filenames like:
      sub9_t9_pre-s100-FOOOF.csv -> (sub=9, t_num=9, cond='pre')

    Only relies on:
      - first token contains 'sub*'
      - second token contains 't*'
      - third token begins with 'pre' or 'post'
    """
    base = os.path.basename(path)
    stem = base[:-4] if base.lower().endswith(".csv") else base
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Filename does not match convention: {base}")
    m_sub = re.search(r"sub(\d+)", parts[0], flags=re.I)
    m_day = re.search(r"t(\d+)",   parts[1], flags=re.I)
    cond  = parts[2].split("-")[0].lower()
    if not (m_sub and m_day and cond in ("pre","post")):
        raise ValueError(f"Cannot parse: {base}")
    return int(m_sub.group(1)), int(m_day.group(1)), cond  # Day uses t_num directly

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    required = {"channel","offset","exponent"}
    if not required.issubset(df.columns):
        raise ValueError(f"{os.path.basename(path)} missing columns {required}")
    return df

def iter_measure_rows_s100(df: pd.DataFrame):
    """
    Use the channel text as MeasureID; skip 'FP2'.
    Yields: (MeasureID, offset, exponent)
    """
    for _, r in df.iterrows():
        ch = str(r["channel"]).strip()
        if ch.upper() == "FP2":
            continue
        yield ch, float(r["offset"]), float(r["exponent"])

# ---------- Main ----------
def main():
    files = sorted(sum((glob.glob(p) for p in PATTERNS), []))
    if not files:
        print("[WARN] No *pre-s100*.csv or *post-s100*.csv found")
        return

    off_map = defaultdict(lambda: defaultdict(lambda: {'pre':{}, 'post':{}}))  # subj -> t -> cond -> meas->val
    exp_map = defaultdict(lambda: defaultdict(lambda: {'pre':{}, 'post':{}}))

    for f in files:
        try:
            subj, t_num, cond = parse_filename(f)
            df = load_csv(f)
            for meas, off, exp in iter_measure_rows_s100(df):
                off_map[subj][t_num][cond][meas] = off
                exp_map[subj][t_num][cond][meas] = exp
        except Exception as e:
            print(f"[SKIP] {f}: {e}")

    # Build long-format rows:
    # For each Day=t_num, output same-day pre (1), same-day post (3),
    # then next-day pre mapped back to current Day (4).
    rows_off, rows_exp = [], []
    for subj in sorted(off_map.keys()):
        days = sorted(off_map[subj].keys())
        for idx, t_num in enumerate(days):
            day_val = int(t_num)

            for dmap, rows in ((off_map, rows_off), (exp_map, rows_exp)):
                for meas, val in dmap[subj][t_num]['pre'].items():
                    rows.append({"Subject": subj, "Day": day_val, "Condition": 1, "MeasureID": meas, "Value": val})

            for dmap, rows in ((off_map, rows_off), (exp_map, rows_exp)):
                for meas, val in dmap[subj][t_num]['post'].items():
                    rows.append({"Subject": subj, "Day": day_val, "Condition": 3, "MeasureID": meas, "Value": val})

            if idx < len(days) - 1:
                t_next = days[idx + 1]
                for dmap, rows in ((off_map, rows_off), (exp_map, rows_exp)):
                    for meas, val in dmap[subj][t_next]['pre'].items():
                        rows.append({"Subject": subj, "Day": day_val, "Condition": 4, "MeasureID": meas, "Value": val})

    def finalize(rows, out_path):
        T = pd.DataFrame(rows)
        if T.empty:
            print(f"[WARN] No data: {out_path}")
            return
        T["meas_rank"] = T["MeasureID"].map(MEAS_RANK).fillna(999).astype(int)
        T["cond_rank"] = T["Condition"].map(COND_RANK).fillna(99).astype(int)
        T["Day"] = T["Day"].astype(int)
        T = (T.sort_values(["meas_rank","Subject","Day","cond_rank"])
              .drop(columns=["meas_rank","cond_rank"])
              .reset_index(drop=True))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        T.to_csv(out_path, index=False)
        print(f"[OK] Wrote: {out_path} (n={len(T)})")

    finalize(rows_off, OUT_OFFSET)
    finalize(rows_exp,  OUT_EXP)

if __name__ == "__main__":
    main()
