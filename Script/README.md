"""
RESULT 4 — Region-size-aware waste forecasting and bin-demand estimation
========================================================================

A single-file implementation designed to run from VS Code.

What this script compares
-------------------------
1. Global Linear Regression (baseline)
2. Global SVM (RBF kernel approximation + LinearSVR)
3. Global ANN with Swish activation, Huber loss and Adam
4. Global ANN with Linear activation, Huber loss and Adam
5. City-size segmented ANN Swish (separate Small / Medium / Large models)
6. Population-tier-balanced ANN Swish (weighted Huber loss)
7. Quantile ANN Swish (predicts q10 / q50 / q90; q50 is the point prediction)
8. Gaussian Naive Bayes separately for capacity-overload classification

Core target
-----------
log1p(kg of waste per person per day)

After prediction, the script converts the target back to kg/person/day, then
reconstructs daily city waste in tons and an estimated weekly bin requirement.

IMPORTANT DATA LIMITATIONS
--------------------------
- The CSV contains monthly city/waste-type rows, not weekly measurements.
- The city-month target is the SUM of recorded waste-type rows. The source has
  incomplete waste-category coverage, so this may undercount city-wide waste.
- The source does not contain measured total physical bin requirements,
  usable kg/bin, or verified collection cycles. Bin-count metrics are therefore
  scenario proxies using BIN_CAPACITY_KG and Garbage_Collection_Frequency.
- Garbage_Collection_Frequency is assumed to mean emptying / collection cycles
  per week. Change that assumption if the source definition differs.
- Smart_Bins_Count is not treated as total physical bins.

Run
---
1. Put this file and Waste_Management_India_20K.csv in the same folder.
2. Install: pip install pandas numpy scipy scikit-learn joblib torch
3. Run: python result4_from_scratch.py

Optional:
    python result4_from_scratch.py --data path/to/file.csv --output-dir RESULT_4

All feature selection, imputation, encoding, scaling, city-size cutoffs, and
sample weights are learned from each training fold only. The final test period
is held out chronologically and never used for model selection.
"""
