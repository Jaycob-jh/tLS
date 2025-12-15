#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Summarize FOOOF (Yeo7 resolution) into long-format tables.

Inputs
  - From /results/FOOOF/sub*/:
      *pre-net*.csv and *post-net*.csv

Outputs
  - /GPFS/.../results/offset_yeo7.csv
  - /GPFS/.../results/exponent_yeo7.csv

Output columns
  - Subject, Day, Condition, MeasureID, Value

Day rule
  - Day equals the numeric part of t in the filename (e.g., t1 -> Day=1, t3 -> Day=3).

Row logic (per current Day=t)
  1) same-day pre  -> Condition=1
  2) same-day post -> Condition=3
  3) next-day pre  -> Condition=4 (but Day remains the current t)
"""

import os, re, glob
import pandas as pd
from collections import defaultdict

# ---------- Paths ----------
ROOT_FOOOF = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results/FOOOF"
OUT_DIR    = "/GPFS/cuizaixu_lab_permanent/jiahai/tLS_EEG/results"
PATTERNS   = [
    os.path.join(ROOT_FOOOF, "sub*", "*pre-net*.csv"),
    os.path.join(ROOT_FOOOF, "sub*", "*post-net*.csv"),
]
OUT_OFFSET = os.path.join(OUT_DIR, "offset_yeo7.csv")
OUT_EXP    = os.path.join(OUT_DIR, "exponent_yeo7.csv")

# ---------- Mapping and fixed order ----------
# Map numeric Yeo7 labels to network names
NUM2NAME = {"1":"Visual","2":"SM","3":"DA","4":"SA","5":"Limbic","6":"Control","7":"Default"}

# Fixed display/order (L/R pairs; Limbic is excluded later)
BASE_ORDER = ["Control","Control","DA","DA","Default","Default","SA","SA","SM","SM","Visual","Visual"]
SIDE_ORDER = ["L","R","L","R","L","R","L","R","L","R","L","R"]
MEASURE_ORDER = [f"{b}_{s}" for b, s in zip(BASE_ORDER, SIDE_ORDER)]

COND_RANK = {1:0, 3:1, 4:2}
MEAS_RANK = {m:i for i, m in enumerate(MEASURE_ORDER)}

# ---------- Utilities ----------
def parse_filename(path: str):
    """
    Parse filenames like:
      sub1_t3_pre-net-*.csv -> (sub:int, t_num:int, cond:'pre'|'post')

    Day uses t_num (e.g., 3).
    """
    base = os.path.basename(path)
    stem = base[:-4] if base.lower().endswith(".csv") else base
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Filename does not match convention: {base}")
    m_sub = re.search(r"sub(\d+)", parts[0], flags=re.I)
    m_day = re.search(r"(t\d+)",   parts[1], flags=re.I)
    cond  = parts[2].split("-")[0].lower()
    if not (m_sub and m_day and cond in ("pre","post")):
        raise ValueError(f"Cannot parse: {base}")
    t_num = int(re.search(r"\d+", m_day.group(1)).group(0))
    return int(m_sub.group(1)), t_num, cond

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    required = {"channel","offset","exponent"}
    if not required.issubset(df.columns):
        raise ValueError(f"{os.path.basename(path)} missing columns {required}")
    return df

def iter_measure_rows(df: pd.DataFrame):
    """
    Extract (1..7) with L/R from the 'channel' column; skip Limbic and non-(1..7) (e.g., FP2).
    Yields: (MeasureID, offset, exponent), where MeasureID = <Network>_<L|R>
    """
    for _, r in df.iterrows():
        ch = str(r["channel"]).strip()
        m = re.match(r"^(\d+)\s*([LR])$", ch, flags=re.I)
        if not m:
            continue
        num, side = m.group(1), m.group(2).upper()
        base = NUM2NAME.get(num)
        if base is None or base == "Limbic":
            continue
        meas = f"{base}_{side}"
        yield meas, float(r["offset"]), float(r["exponent"])

# ---------- Main ----------
def main():
    files = sorted(sum((glob.glob(p) for p in PATTERNS), []))
    if not files:
        print("[WARN] No *pre-net*.csv or *post-net*.csv found")
        return

    # subject -> t_num -> {'pre':{meas->val}, 'post':{...}}
    off_map = defaultdict(lambda: defaultdict(lambda: {'pre':{}, 'post':{}}))
    exp_map = defaultdict(lambda: defaultdict(lambda: {'pre':{}, 'post':{}}))

    for f in files:
        try:
            subj, t_num, cond = parse_filename(f)
            df = load_csv(f)
            for meas, off, exp in iter_measure_rows(df):
                off_map[subj][t_num][cond][meas] = off
                exp_map[subj][t_num][cond][meas] = exp
        except Exception as e:
            print(f"[SKIP] {f}: {e}")

    # Build long-format rows per Day=t_num in order: 1 -> 3 -> 4
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
