#!/bin/bash
#SBATCH -p q_fat_l
#SBATCH -c 6
#SBATCH -J fooof
#SBATCH -o fooof_%j.out
#SBATCH -e fooof_%j.err


python s4_mapyeo7.py
