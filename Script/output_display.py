import pandas as pd

df = pd.read_csv("RESULT_4/holdout_predictions.csv")

region = "North"

region_data = df[
    df["Region"].str.lower() == region.lower()
]

columns = [
    "City",
    "Region",
    "Date",
    "actual_bins_proxy",
    "pred_bins__Global ANN Swish Huber Adam",
    "pred_bins__Segmented ANN Swish",
    "pred_bins__Population-weighted ANN Swish",
    "pred_bins__Quantile ANN Swish q50"
]

print(region_data[columns].to_string(index=False))