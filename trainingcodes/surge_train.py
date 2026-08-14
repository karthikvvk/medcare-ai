# =========================================================
# MEDCARE PHARMA - DEMAND SURGE DETECTION
# SINGLE DATASET VERSION (Handling categorical objects)
# + TOP 10 SURGE PRODUCTS OUTPUT
# =========================================================

#pip install -q xgboost scikit-learn pandas numpy matplotlib seaborn pickle

import os
import glob
import warnings
import json
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from xgboost import XGBClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import classification_report, f1_score
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import RobustScaler

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", None)

demand_file = "demand_surge.csv"
if not os.path.exists(demand_file):
    candidates = glob.glob("/content/*.csv")
    found = None
    for file in candidates:
        try:
            temp = pd.read_csv(file, nrows=5)
            if {"sku_id", "dc_id", "date", "demand_qty"}.issubset(set(temp.columns.str.strip().str.lower())):
                found = file
                break
        except: pass
    demand_file = found if found else demand_file

df = pd.read_csv(demand_file)
df.columns = df.columns.str.strip().str.lower()
if "product_name" not in df.columns: df["product_name"] = df["sku_id"].astype(str)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["demand_qty"] = pd.to_numeric(df["demand_qty"], errors="coerce")
df = df.dropna(subset=["date", "sku_id", "dc_id", "demand_qty"])
df = df.sort_values(["sku_id", "dc_id", "date"]).reset_index(drop=True)

print(f"Initial Rows: {len(df)}")

# --- FEATURE ENGINEERING ---
group = df.groupby(["sku_id", "dc_id"], group_keys=False)
df["lag_1"] = group["demand_qty"].shift(1)
df["rolling_mean_7"] = group["demand_qty"].transform(lambda x: x.shift(1).rolling(7, min_periods=3).mean())

future_columns = []
for i in range(1, 4):
    col = f"future_day_{i}"
    df[col] = group["demand_qty"].shift(-i)
    future_columns.append(col)
df["future_sum"] = df[future_columns].sum(axis=1)
df["surge_ratio"] = df["future_sum"] / (df["rolling_mean_7"] * 3 + 1e-8)

df = df.dropna(subset=["lag_1", "rolling_mean_7", "future_sum"]).reset_index(drop=True)
print(f"Rows remaining: {len(df)}")

# --- TARGET ---
threshold = max(1.2, df["surge_ratio"].quantile(0.8))
df["surge"] = (df["surge_ratio"] >= threshold).astype(int)

# --- ENCODING CATEGORICALS ---
# Automatically detect all object/string columns to encode
cat_cols = df.select_dtypes(include=['object']).columns.tolist()
if 'product_name' in cat_cols: cat_cols.remove('product_name')

# Include sku_id and dc_id if they aren't already string (sometimes they are numeric)
for c in ['sku_id', 'dc_id']:
    if c in df.columns and c not in cat_cols: cat_cols.append(c)

df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)

# --- MODELING ---
exclude = ["date", "product_name", "future_sum", "surge_ratio", "surge"] + future_columns
features = [c for c in df_encoded.columns if c not in exclude]

X = df_encoded[features].select_dtypes(include=[np.number]).fillna(0)
y = df_encoded["surge"]

dates = np.sort(df_encoded["date"].unique())
cutoff = dates[int(len(dates) * 0.8)]
train_mask = df_encoded["date"] < cutoff

X_train, y_train = X[train_mask], y[train_mask]
X_test, y_test = X[~train_mask], y[~train_mask]

model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
model.fit(X_train, y_train)

print("Model trained successfully.")
print(classification_report(y_test, model.predict(X_test), zero_division=0))

# =========================================================
# PREDICTIONS + RISK SCORING ON TEST SET
# =========================================================

if len(X_test) == 0:
    raise ValueError(
        "Test set is empty after the chronological split — there isn't "
        "enough date range in demand_surge.csv to hold out a test period. "
        "Add more historical dates or lower the split fraction (currently 80/20)."
    )

test_probs = model.predict_proba(X_test)[:, 1]

# df and df_encoded share the same index, so we can pull original
# (unencoded) columns like product_name, dc_id, demand_qty back in.
test_original = df.loc[~train_mask].copy()

result = pd.DataFrame({
    "sku_id": test_original["sku_id"].values,
    "product_name": test_original["product_name"].values,
    "dc_id": test_original["dc_id"].values,
    "date": test_original["date"].values,
    "current_demand": test_original["demand_qty"].values,
    "baseline_demand": test_original["rolling_mean_7"].values,
    "forecast_demand": (test_original["future_sum"] / 3).values,
    "surge_probability": test_probs
})

result["demand_increase_pct"] = (
    (result["forecast_demand"] / (result["baseline_demand"] + 1e-8)) - 1
) * 100

def risk_level(p):
    if p >= 0.80:
        return "CRITICAL"
    elif p >= 0.60:
        return "HIGH"
    elif p >= 0.35:
        return "MEDIUM"
    else:
        return "LOW"

result["risk_level"] = result["surge_probability"].apply(risk_level)
result["surge_prediction"] = (result["surge_probability"] >= 0.5).astype(int)
result["surge_status"] = np.where(result["surge_prediction"] == 1, "SURGE", "NO_SURGE")
result["surge_risk_score"] = (result["surge_probability"] * 100).round(1)
result["surge_probability_pct"] = (result["surge_probability"] * 100).round(1)

result = result.sort_values("surge_probability", ascending=False).reset_index(drop=True)

top_10 = result.head(10).copy()

# =========================================================
# PRINTED TOP 10
# =========================================================

print("\n" + "=" * 70)
print("TOP 10 HIGHEST DEMAND SURGE PRODUCTS")
print("=" * 70)

for rank, row in enumerate(top_10.itertuples(), 1):
    print(f"""
{'-' * 70}
RANK #{rank}
{'-' * 70}
SKU ID                 : {row.sku_id}
Product Name           : {row.product_name}
DC                     : {row.dc_id}

Current Demand         : {row.current_demand:.0f} units/day
Baseline Demand        : {row.baseline_demand:.0f} units/day
Forecast Demand (3d)   : {row.forecast_demand:.0f} units/day
Demand Increase        : {row.demand_increase_pct:+.1f}%

Surge Prediction       : {row.surge_status}
Surge Probability      : {row.surge_probability_pct:.1f}%
Surge Risk Score       : {row.surge_risk_score:.1f} / 100
Risk Level             : {row.risk_level}
""")

# =========================================================
# JSON EXPORT (same shape as your sample output)
# =========================================================

json_records = [
    {
        "sku": row.sku_id,
        "product_name": row.product_name,
        "dc": row.dc_id,
        "current_demand": float(row.current_demand),
        "baseline_demand": round(float(row.baseline_demand), 1),
        "forecast_demand_3d": round(float(row.forecast_demand), 1),
        "demand_increase_percent": round(float(row.demand_increase_pct), 1),
        "surge_probability": round(float(row.surge_probability_pct), 1),
        "surge_risk_score": round(float(row.surge_risk_score), 1),
        "surge_prediction": int(row.surge_prediction),
        "surge_status": row.surge_status,
        "risk_level": row.risk_level,
    }
    for row in top_10.itertuples()
]

with open("top_10_surge_products.json", "w") as f:
    json.dump(json_records, f, indent=2, default=str)

print(json.dumps(json_records, indent=2, default=str))

# =========================================================
# SAVE CSVs + MODEL
# =========================================================
result.to_csv("surge_predictions.csv", index=False)
top_10.to_csv("top_10_surge_products.csv", index=False)

with open("demand_surge_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("\nSaved:")
print(" - surge_predictions.csv (all test rows)")
print(" - top_10_surge_products.csv")
print(" - top_10_surge_products.json")
print(" - demand_surge_model.pkl")