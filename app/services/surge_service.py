"""
Surge Prediction Service
========================
Reads the pre-trained XGBoost demand-surge detection artefacts produced by
surge_related_programs_temp_dir/surge_train.py:

  - demand_surge_model.pkl        (trained XGBClassifier)
  - surge_predictions.csv         (scored test-set rows, all SKUs × DCs)
  - top_10_surge_products.json    (top-10 highest surge-risk records)

The service does NOT re-train on each request.  It loads and caches the CSV
and JSON outputs, then returns filtered/summarised views to the API layer.
"""

import json
import os
import pickle
import pandas as pd
from typing import Optional, List, Dict, Any

from app.core.logging_config import logger

# ---------------------------------------------------------------------------
# Paths (relative to project root, matching how expiry_service references
# its temp dir)
# ---------------------------------------------------------------------------

_BASE = os.path.join(os.path.dirname(__file__), "../../surge_related_programs_temp_dir")

_PREDICTIONS_CSV  = os.path.join(_BASE, "surge_predictions.csv")
_TOP10_JSON       = os.path.join(_BASE, "top_10_surge_products.json")
_MODEL_PKL        = os.path.join(_BASE, "demand_surge_model.pkl")

# ---------------------------------------------------------------------------
# Module-level cache (loaded once per process)
# ---------------------------------------------------------------------------

_predictions_df: Optional[pd.DataFrame] = None
_top10_records:  Optional[List[dict]]   = None
_model = None


def _load_predictions() -> pd.DataFrame:
    global _predictions_df
    if _predictions_df is not None:
        return _predictions_df
    try:
        df = pd.read_csv(_PREDICTIONS_CSV)
        df.columns = df.columns.str.strip().str.lower()
        # Normalise risk_level to uppercase just in case
        if "risk_level" in df.columns:
            df["risk_level"] = df["risk_level"].str.upper()
        _predictions_df = df
        logger.info(f"Surge predictions loaded: {len(df)} rows from {_PREDICTIONS_CSV}")
    except Exception as e:
        logger.error(f"Failed to load surge_predictions.csv: {e}")
        _predictions_df = pd.DataFrame()
    return _predictions_df


def _load_top10() -> List[dict]:
    global _top10_records
    if _top10_records is not None:
        return _top10_records
    try:
        with open(_TOP10_JSON, "r") as f:
            _top10_records = json.load(f)
        logger.info(f"Top-10 surge products loaded from {_TOP10_JSON}")
    except Exception as e:
        logger.error(f"Failed to load top_10_surge_products.json: {e}")
        _top10_records = []
    return _top10_records


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        with open(_MODEL_PKL, "rb") as f:
            _model = pickle.load(f)
        logger.info("Surge XGBoost model loaded from pkl.")
    except Exception as e:
        logger.warning(f"Could not load surge model pkl: {e}")
        _model = None
    return _model


# ---------------------------------------------------------------------------
# Public API used by routes_surge.py
# ---------------------------------------------------------------------------

RISK_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

RISK_COLORS = {
    "CRITICAL": "#f43f5e",
    "HIGH":     "#f97316",
    "MEDIUM":   "#f59e0b",
    "LOW":      "#6366f1",
}


def get_summary() -> Dict[str, Any]:
    """Return high-level KPI summary across all predictions."""
    df = _load_predictions()
    if df.empty:
        return {
            "total_records": 0,
            "surge_count": 0,
            "no_surge_count": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "avg_surge_probability": 0.0,
            "avg_surge_risk_score": 0.0,
        }

    surge_col = "surge_prediction" if "surge_prediction" in df.columns else None
    prob_col  = "surge_probability_pct" if "surge_probability_pct" in df.columns else "surge_probability"

    return {
        "total_records":        int(len(df)),
        "surge_count":          int((df[surge_col] == 1).sum()) if surge_col else 0,
        "no_surge_count":       int((df[surge_col] == 0).sum()) if surge_col else 0,
        "critical_count":       int((df["risk_level"] == "CRITICAL").sum()),
        "high_count":           int((df["risk_level"] == "HIGH").sum()),
        "medium_count":         int((df["risk_level"] == "MEDIUM").sum()),
        "low_count":            int((df["risk_level"] == "LOW").sum()),
        "avg_surge_probability": round(float(df[prob_col].mean()), 1) if prob_col in df.columns else 0.0,
        "avg_surge_risk_score":  round(float(df["surge_risk_score"].mean()), 1) if "surge_risk_score" in df.columns else 0.0,
    }


def get_predictions(risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all predictions, optionally filtered by risk_level."""
    df = _load_predictions()
    if df.empty:
        return []

    if risk_level:
        df = df[df["risk_level"] == risk_level.upper()]

    records = []
    for _, row in df.iterrows():
        records.append({
            "sku_id":                 str(row.get("sku_id", "")),
            "product_name":           str(row.get("product_name", "")),
            "dc_id":                  str(row.get("dc_id", "")),
            "date":                   str(row.get("date", "")),
            "current_demand":         _safe_float(row.get("current_demand", 0)),
            "baseline_demand":        _safe_float(row.get("baseline_demand", 0)),
            "forecast_demand":        _safe_float(row.get("forecast_demand", 0)),
            "surge_probability":      _safe_float(row.get("surge_probability_pct", row.get("surge_probability", 0))),
            "surge_risk_score":       _safe_float(row.get("surge_risk_score", 0)),
            "demand_increase_pct":    _safe_float(row.get("demand_increase_pct", 0)),
            "risk_level":             str(row.get("risk_level", "LOW")),
            "surge_status":           str(row.get("surge_status", "NO_SURGE")),
            "surge_prediction":       int(row.get("surge_prediction", 0)),
        })
    return records


def get_top_products() -> List[Dict[str, Any]]:
    """Return the top-10 surge products from the pre-generated JSON."""
    return _load_top10()


def get_model_info() -> Dict[str, Any]:
    """Return basic metadata about the loaded model."""
    model = _load_model()
    if model is None:
        return {"loaded": False}
    return {
        "loaded":        True,
        "model_type":    type(model).__name__,
        "n_estimators":  getattr(model, "n_estimators", None),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val, default: float = 0.0) -> float:
    try:
        return round(float(val), 2)
    except (TypeError, ValueError):
        return default
