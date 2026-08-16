"""
Expiry Prediction Service
=========================
Loads pre-generated expiry_predictions.json from data/processed/ and
builds the same structured response the API / frontend expects.

No DB queries — mirrors the pattern used by surge_service.py so the
endpoint works even when the database is empty.

JSON schema (per record):
  SKU, product_name, DC, dc_location, batch, mfg_date, expiry_date,
  on_hand_quantity, available_on_hand_quantity,
  days_to_expiry, weeks_to_expiry,
  expected_weekly_demand, expected_demand_before_expiry,
  expected_remaining_stock, inventory_coverage_weeks,
  expiry_urgency_score, inventory_pressure_score, coverage_risk_score,
  expiry_risk_score, expected_writeoff_quantity,
  expiry_risk, recommended_action, allocation_priority
"""

import json
import os
from typing import Optional, List, Dict, Any

from app.core.logging_config import logger

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR         = os.path.join(os.path.dirname(__file__), "../../data/processed")
_PREDICTIONS_JSON = os.path.join(_DATA_DIR, "expiry_predictions.json")
_WEIGHTS_PATH     = os.path.join(_DATA_DIR, "expiry_model_weights.json")
_DCS_CSV          = os.path.join(_DATA_DIR, "dcs.csv")
_SKUS_CSV         = os.path.join(_DATA_DIR, "skus.csv")

# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_predictions: Optional[List[dict]] = None
_model_weights: Optional[dict]     = None
_dc_name_map: Optional[Dict[str, str]] = None
_sku_cost_map: Optional[Dict[str, float]] = None


def _load_dc_names() -> Dict[str, str]:
    """Returns a dict mapping dc_id -> dc_name from dcs.csv."""
    global _dc_name_map
    if _dc_name_map is not None:
        return _dc_name_map
    _dc_name_map = {}
    try:
        with open(_DCS_CSV, "r") as f:
            header = f.readline().strip().split(",")
            id_col   = header.index("dc_id")
            name_col = header.index("name")
            for line in f:
                parts = line.strip().split(",")
                if len(parts) > max(id_col, name_col):
                    _dc_name_map[parts[id_col]] = parts[name_col]
        logger.info(f"DC name map loaded: {_dc_name_map}")
    except Exception as e:
        logger.warning(f"Could not load dcs.csv for DC name map: {e}")
    return _dc_name_map


def _load_sku_unit_costs() -> Dict[str, float]:
    """Returns a dict mapping sku_id -> unit_cost from skus.csv."""
    global _sku_cost_map
    if _sku_cost_map is not None:
        return _sku_cost_map
    _sku_cost_map = {
        "MED001": 30.67, "MED002": 31.76, "MED003": 67.67, "MED004": 97.67,
        "MED005": 92.80, "MED006": 74.43, "MED007": 14.06, "MED008": 31.21,
    }
    try:
        with open(_SKUS_CSV, "r") as f:
            header = f.readline().strip().split(",")
            id_col = header.index("sku_id")
            cost_col = header.index("unit_cost")
            for line in f:
                parts = line.strip().split(",")
                if len(parts) > max(id_col, cost_col):
                    try:
                        _sku_cost_map[parts[id_col]] = float(parts[cost_col])
                    except ValueError:
                        pass
    except Exception as e:
        logger.warning(f"Could not load skus.csv for unit costs: {e}")
    return _sku_cost_map


def _get_mock_predictions() -> List[dict]:
    return [
        {
            "batch_id": "BAT-2026-081",
            "sku_id": "MED003",
            "sku_name": "Medication-EME-3",
            "dc_id": "DC001",
            "dc_name": "Chennai DC",
            "dc_location": "Chennai",
            "manufacturing_date": "2025-08-15",
            "expiry_date": "2026-08-25",
            "days_to_expiry": 13,
            "weeks_to_expiry": 1.86,
            "available_quantity": 450,
            "expected_weekly_demand": 35.0,
            "expected_demand_before_expiry": 66.5,
            "expected_remaining_stock": 383.5,
            "inventory_coverage_weeks": 12.86,
            "expiry_urgency_score": 0.95,
            "inventory_pressure_score": 0.92,
            "coverage_risk_score": 0.90,
            "expiry_risk_score": 0.93,
            "expected_writeoff_quantity": 384,
            "expiry_risk": "CRITICAL",
            "recommended_action": "EXPEDITE_FEFO",
            "unit_cost": 67.67,
            "projected_loss_inr": 25985.28,
        },
        {
            "batch_id": "BAT-2026-114",
            "sku_id": "MED005",
            "sku_name": "Medication-RES-5",
            "dc_id": "DC004",
            "dc_name": "Mumbai DC",
            "dc_location": "Mumbai",
            "manufacturing_date": "2025-09-01",
            "expiry_date": "2026-08-30",
            "days_to_expiry": 18,
            "weeks_to_expiry": 2.57,
            "available_quantity": 320,
            "expected_weekly_demand": 25.0,
            "expected_demand_before_expiry": 65.0,
            "expected_remaining_stock": 255.0,
            "inventory_coverage_weeks": 12.80,
            "expiry_urgency_score": 0.90,
            "inventory_pressure_score": 0.85,
            "coverage_risk_score": 0.88,
            "expiry_risk_score": 0.88,
            "expected_writeoff_quantity": 255,
            "expiry_risk": "CRITICAL",
            "recommended_action": "URGENT_ALLOCATION",
            "unit_cost": 92.80,
            "projected_loss_inr": 23664.00,
        },
        {
            "batch_id": "BAT-2026-205",
            "sku_id": "MED002",
            "sku_name": "Medication-GAS-2",
            "dc_id": "DC002",
            "dc_name": "Bangalore DC",
            "dc_location": "Bangalore",
            "manufacturing_date": "2025-10-10",
            "expiry_date": "2026-09-18",
            "days_to_expiry": 37,
            "weeks_to_expiry": 5.29,
            "available_quantity": 600,
            "expected_weekly_demand": 45.0,
            "expected_demand_before_expiry": 238.5,
            "expected_remaining_stock": 361.5,
            "inventory_coverage_weeks": 13.33,
            "expiry_urgency_score": 0.65,
            "inventory_pressure_score": 0.68,
            "coverage_risk_score": 0.70,
            "expiry_risk_score": 0.68,
            "expected_writeoff_quantity": 362,
            "expiry_risk": "HIGH",
            "recommended_action": "INTER_DC_TRANSFER",
            "unit_cost": 31.76,
            "projected_loss_inr": 11497.12,
        },
        {
            "batch_id": "BAT-2026-319",
            "sku_id": "MED004",
            "sku_name": "Medication-DIA-4",
            "dc_id": "DC005",
            "dc_name": "Delhi DC",
            "dc_location": "Delhi",
            "manufacturing_date": "2025-11-01",
            "expiry_date": "2026-09-28",
            "days_to_expiry": 47,
            "weeks_to_expiry": 6.71,
            "available_quantity": 500,
            "expected_weekly_demand": 40.0,
            "expected_demand_before_expiry": 268.0,
            "expected_remaining_stock": 232.0,
            "inventory_coverage_weeks": 12.50,
            "expiry_urgency_score": 0.55,
            "inventory_pressure_score": 0.60,
            "coverage_risk_score": 0.58,
            "expiry_risk_score": 0.58,
            "expected_writeoff_quantity": 232,
            "expiry_risk": "HIGH",
            "recommended_action": "REDUCE_ORDER",
            "unit_cost": 97.67,
            "projected_loss_inr": 22659.44,
        },
        {
            "batch_id": "BAT-2026-442",
            "sku_id": "MED008",
            "sku_name": "Medication-CAR-8",
            "dc_id": "DC003",
            "dc_name": "Hyderabad DC",
            "dc_location": "Hyderabad",
            "manufacturing_date": "2025-11-15",
            "expiry_date": "2026-10-12",
            "days_to_expiry": 61,
            "weeks_to_expiry": 8.71,
            "available_quantity": 400,
            "expected_weekly_demand": 30.0,
            "expected_demand_before_expiry": 261.0,
            "expected_remaining_stock": 139.0,
            "inventory_coverage_weeks": 13.33,
            "expiry_urgency_score": 0.45,
            "inventory_pressure_score": 0.50,
            "coverage_risk_score": 0.48,
            "expiry_risk_score": 0.48,
            "expected_writeoff_quantity": 139,
            "expiry_risk": "WATCH",
            "recommended_action": "MONITOR_CONSUMPTION",
            "unit_cost": 31.21,
            "projected_loss_inr": 4338.19,
        },
        {
            "batch_id": "BAT-2026-590",
            "sku_id": "MED001",
            "sku_name": "Medication-ANA-1",
            "dc_id": "DC006",
            "dc_name": "Kolkata DC",
            "dc_location": "Kolkata",
            "manufacturing_date": "2026-01-10",
            "expiry_date": "2027-02-15",
            "days_to_expiry": 187,
            "weeks_to_expiry": 26.71,
            "available_quantity": 850,
            "expected_weekly_demand": 80.0,
            "expected_demand_before_expiry": 850.0,
            "expected_remaining_stock": 0.0,
            "inventory_coverage_weeks": 10.62,
            "expiry_urgency_score": 0.10,
            "inventory_pressure_score": 0.15,
            "coverage_risk_score": 0.10,
            "expiry_risk_score": 0.12,
            "expected_writeoff_quantity": 0,
            "expiry_risk": "LOW",
            "recommended_action": "NORMAL_ALLOCATION",
            "unit_cost": 30.67,
            "projected_loss_inr": 0.00,
        },
    ]


def _load_predictions(force_reload: bool = False) -> List[dict]:
    global _predictions
    if not force_reload and _predictions is not None:
        return _predictions
    try:
        if os.path.exists(_PREDICTIONS_JSON):
            with open(_PREDICTIONS_JSON, "r") as f:
                raw = json.load(f)
            dc_names = _load_dc_names()
            costs = _load_sku_unit_costs()
            normalised = []
            for r in raw:
                dc_id = str(r.get("DC", r.get("dc_id", "")))
                sku_id = str(r.get("SKU", r.get("sku_id", "")))
                unit_cost = float(r.get("unit_cost") or costs.get(sku_id, 25.0))
                writeoff = int(float(r.get("expected_writeoff_quantity", 0)))
                proj_loss = float(r.get("projected_loss_inr") or round(writeoff * unit_cost, 2))

                normalised.append({
                    "batch_id":                    str(r.get("batch", r.get("batch_id", ""))),
                    "sku_id":                      sku_id,
                    "sku_name":                    str(r.get("product_name", r.get("sku_name", ""))),
                    "dc_id":                       dc_id,
                    "dc_name":                     dc_names.get(dc_id, str(r.get("dc_name", dc_id))),
                    "dc_location":                 str(r.get("dc_location", "")),
                    "manufacturing_date":           str(r.get("mfg_date", r.get("manufacturing_date", ""))),
                    "expiry_date":                 str(r.get("expiry_date", "")),
                    "days_to_expiry":              int(r.get("days_to_expiry", 0)),
                    "weeks_to_expiry":             round(float(r.get("weeks_to_expiry", 0)), 2),
                    "available_quantity":          int(float(r.get("available_on_hand_quantity", r.get("available_quantity", r.get("on_hand_quantity", 0))))),
                    "expected_weekly_demand":       round(float(r.get("expected_weekly_demand", 0)), 2),
                    "expected_demand_before_expiry": round(float(r.get("expected_demand_before_expiry", 0)), 2),
                    "expected_remaining_stock":    round(float(r.get("expected_remaining_stock", 0)), 2),
                    "inventory_coverage_weeks":    round(float(r.get("inventory_coverage_weeks", 0)), 2),
                    "expiry_urgency_score":        round(float(r.get("expiry_urgency_score", 0)), 4),
                    "inventory_pressure_score":    round(float(r.get("inventory_pressure_score", 0)), 4),
                    "coverage_risk_score":         round(float(r.get("coverage_risk_score", 0)), 4),
                    "expiry_risk_score":           round(float(r.get("expiry_risk_score", 0)), 4),
                    "expected_writeoff_quantity":  writeoff,
                    "expiry_risk":                 str(r.get("expiry_risk", "LOW")).upper(),
                    "recommended_action":          str(r.get("recommended_action", "NORMAL_ALLOCATION")),
                    "unit_cost":                   round(unit_cost, 2),
                    "projected_loss_inr":          round(proj_loss, 2),
                })
            _predictions = normalised
            logger.info(f"Expiry predictions loaded: {len(normalised)} records from {_PREDICTIONS_JSON}")
        else:
            _predictions = _get_mock_predictions()
    except Exception as e:
        logger.error(f"Failed to load expiry_predictions.json: {e}. Using mock predictions.")
        _predictions = _get_mock_predictions()
    return _predictions


def _load_weights() -> dict:
    global _model_weights
    if _model_weights is not None:
        return _model_weights
    try:
        with open(_WEIGHTS_PATH, "r") as f:
            _model_weights = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load expiry_model_weights.json: {e}. Using defaults.")
        _model_weights = {
            "model_name": "Expiry Aware Allocation Model",
            "formula": "0.40 * expiry_urgency + 0.35 * inventory_pressure + 0.25 * coverage_risk",
            "weights": {
                "expiry_urgency_score": 0.40,
                "inventory_pressure_score": 0.35,
                "coverage_risk_score": 0.25,
            }
        }
    return _model_weights


# ---------------------------------------------------------------------------
# AI Suggestion builder (same logic as before, zero DB dependency)
# ---------------------------------------------------------------------------

def _build_suggestions(items: list, tier: str) -> dict:
    if not items:
        return {
            "status": f"✅ No {tier} risk items detected — inventory is healthy for this category.",
            "steps": ["Monitor inventory → No action required"]
        }

    total_writeoff = sum(i["expected_writeoff_quantity"] for i in items)
    unique_skus    = len(set(i["sku_id"] for i in items))
    unique_dcs     = len(set(i["dc_id"] for i in items))
    earliest_expiry = min(
        (i["days_to_expiry"] for i in items if i["days_to_expiry"] >= 0),
        default=0
    )
    worst = max(items, key=lambda x: x["expiry_risk_score"])

    if tier == "CRITICAL":
        status = (
            f"🚨 CRITICAL — {len(items)} batch(es) across {unique_dcs} warehouse(s) | "
            f"{unique_skus} SKU(s) affected | ~{int(total_writeoff):,} units at write-off risk | "
            f"Earliest expiry: {earliest_expiry} day(s) | "
            f"Worst batch: [{worst['batch_id']}] {worst['sku_name']} @ {worst['dc_name']} "
            f"(score: {worst['expiry_risk_score']:.2f})"
        )
        steps = [
            f"Identify: Flag batch [{worst['batch_id']}] and all CRITICAL batches expiring within 30 days",
            f"Assess: Confirm available qty ({worst['available_quantity']} units) vs projected demand",
            f"Decide: Trigger URGENT_ALLOCATION — inter-DC transfer or emergency dispensing",
            f"Execute: Raise transfer orders to nearest high-demand DC",
            f"Verify: Confirm stock moved and update batch allocation status",
            f"Close: Mark batches as ALLOCATED and remove from CRITICAL queue",
        ]
    elif tier == "HIGH":
        status = (
            f"⚠️ HIGH RISK — {len(items)} batch(es) across {unique_dcs} warehouse(s) | "
            f"{unique_skus} SKU(s) | ~{int(total_writeoff):,} units projected to expire | "
            f"Earliest expiry: {earliest_expiry} day(s) | "
            f"Focus: [{worst['batch_id']}] {worst['sku_name']} @ {worst['dc_name']} "
            f"(score: {worst['expiry_risk_score']:.2f})"
        )
        steps = [
            f"Review: List all HIGH-risk batches sorted by days-to-expiry",
            f"Prioritize: Apply FEFO — dispatch earliest-expiry batches first",
            f"Transfer: Identify receiving DCs with demand shortfall and initiate transfer",
            f"Promote: Consider short-term demand stimulation (prescription alerts, promotions)",
            f"Track: Monitor weekly consumption vs projected write-off",
            f"Escalate: If no improvement in 7 days, escalate to CRITICAL protocol",
        ]
    else:  # WATCH
        status = (
            f"👁️ WATCH — {len(items)} batch(es) across {unique_dcs} warehouse(s) under surveillance | "
            f"{unique_skus} SKU(s) | ~{int(total_writeoff):,} units at long-term risk | "
            f"Earliest expiry: {earliest_expiry} day(s) | "
            f"Top watch: [{worst['batch_id']}] {worst['sku_name']} "
            f"(score: {worst['expiry_risk_score']:.2f})"
        )
        steps = [
            f"Log: Record all WATCH-level batches in the monitoring registry",
            f"Forecast: Re-run demand forecast for affected SKUs next week",
            f"Plan: Pre-schedule inter-DC transfers for batches nearing 60-day window",
            f"Alert: Set automated reminders at 60, 30 and 14 days before expiry",
            f"Review: Reassess risk score weekly — escalate if score exceeds 0.75",
        ]

    return {"status": status, "steps": steps}


# ---------------------------------------------------------------------------
# Warehouse card builder
# ---------------------------------------------------------------------------

def _build_warehouse_cards(predictions: list) -> list:
    dc_map: dict = {}
    for p in predictions:
        dc_id = p["dc_id"]
        if dc_id not in dc_map:
            dc_map[dc_id] = {
                "dc_id":                  dc_id,
                "dc_name":                p["dc_name"],
                "dc_location":            p["dc_location"],
                "total_batches":          0,
                "critical_batches":       0,
                "high_batches":           0,
                "watch_batches":          0,
                "low_batches":            0,
                "total_at_risk_units":    0,
                "total_projected_loss_inr": 0.0,
                "worst_risk_score":       0.0,
                "worst_risk_level":       "LOW",
                "skus_affected":          set(),
            }
        d = dc_map[dc_id]
        d["total_batches"] += 1
        d["skus_affected"].add(p["sku_id"])
        d["total_at_risk_units"]      += p["expected_writeoff_quantity"]
        d["total_projected_loss_inr"] += p["projected_loss_inr"]
        if p["expiry_risk_score"] > d["worst_risk_score"]:
            d["worst_risk_score"] = p["expiry_risk_score"]
            d["worst_risk_level"] = p["expiry_risk"]
        tier_key = f"{p['expiry_risk'].lower()}_batches"
        if tier_key in d:
            d[tier_key] += 1

    result = []
    for dc_id, d in dc_map.items():
        if d["worst_risk_level"] == "LOW" and d["critical_batches"] == 0 and d["high_batches"] == 0 and d["watch_batches"] == 0:
            continue
        result.append({
            "dc_id":                    d["dc_id"],
            "dc_name":                  d["dc_name"],
            "dc_location":              d["dc_location"],
            "total_batches":            d["total_batches"],
            "critical_batches":         d["critical_batches"],
            "high_batches":             d["high_batches"],
            "watch_batches":            d["watch_batches"],
            "low_batches":              d["low_batches"],
            "skus_affected":            len(d["skus_affected"]),
            "total_at_risk_units":      d["total_at_risk_units"],
            "total_projected_loss_inr": round(d["total_projected_loss_inr"], 2),
            "worst_risk_score":         round(d["worst_risk_score"], 4),
            "worst_risk_level":         d["worst_risk_level"],
        })

    _order = {"CRITICAL": 0, "HIGH": 1, "WATCH": 2, "LOW": 3}
    result.sort(key=lambda x: (_order.get(x["worst_risk_level"], 4), -x["worst_risk_score"]))
    return result


# ---------------------------------------------------------------------------
# Main public class — same interface as before, no db argument needed
# ---------------------------------------------------------------------------

class ExpiryPredictionService:
    """
    Reads expiry_predictions.json (pre-generated offline) and returns the
    same structured response the frontend expects.  No live DB queries.
    """

    def run_expiry_model(self, db=None, current_date=None) -> dict:
        """
        Loads predictions from the baked-in JSON file and returns the full
        structured response.  `db` and `current_date` are accepted but ignored
        so the call-site in routes_inventory.py doesn't need to change.
        """
        predictions = _load_predictions(force_reload=True)

        if not predictions:
            logger.warning("expiry_predictions.json is empty or could not be loaded.")
            return _empty_response()

        # Sort by risk score descending
        predictions_sorted = sorted(predictions, key=lambda x: -x["expiry_risk_score"])

        # Tier separation
        critical_items = [p for p in predictions_sorted if p["expiry_risk"] == "CRITICAL"]
        high_items     = [p for p in predictions_sorted if p["expiry_risk"] == "HIGH"]
        watch_items    = [p for p in predictions_sorted if p["expiry_risk"] == "WATCH"]
        low_items      = [p for p in predictions_sorted if p["expiry_risk"] == "LOW"]

        warehouses_at_risk    = _build_warehouse_cards(predictions_sorted)
        suggestions_critical  = _build_suggestions(critical_items, "CRITICAL")
        suggestions_high      = _build_suggestions(high_items,     "HIGH")
        suggestions_watch     = _build_suggestions(watch_items,    "WATCH")

        weights = _load_weights()

        logger.info(
            f"ExpiryPredictionService (JSON mode): "
            f"CRITICAL={len(critical_items)}, HIGH={len(high_items)}, "
            f"WATCH={len(watch_items)}, LOW={len(low_items)}"
        )

        return {
            "warehouses_at_risk":   warehouses_at_risk,
            "critical_items":       critical_items,
            "high_items":           high_items,
            "watch_items":          watch_items,
            "low_items":            low_items,
            "suggestions_critical": suggestions_critical,
            "suggestions_high":     suggestions_high,
            "suggestions_watch":    suggestions_watch,
            "summary": {
                "total_batches":            len(predictions_sorted),
                "critical_count":           len(critical_items),
                "high_count":               len(high_items),
                "watch_count":              len(watch_items),
                "low_count":               len(low_items),
                "total_at_risk_units":      sum(p["expected_writeoff_quantity"] for p in predictions_sorted),
                "total_projected_loss_inr": round(sum(p["projected_loss_inr"] for p in predictions_sorted), 2),
                "model_name":              weights.get("model_name", "Expiry Aware Allocation Model"),
                "model_formula":           weights.get("formula", ""),
            }
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_response() -> dict:
    weights = _load_weights()
    return {
        "warehouses_at_risk":   [],
        "critical_items":       [],
        "high_items":           [],
        "watch_items":          [],
        "low_items":            [],
        "suggestions_critical": {"status": "No expiry prediction data found.", "steps": []},
        "suggestions_high":     {"status": "No expiry prediction data found.", "steps": []},
        "suggestions_watch":    {"status": "No expiry prediction data found.", "steps": []},
        "summary": {
            "total_batches":            0,
            "critical_count":           0,
            "high_count":               0,
            "watch_count":              0,
            "low_count":                0,
            "total_at_risk_units":      0,
            "total_projected_loss_inr": 0.0,
            "model_name":              weights.get("model_name", "Expiry Aware Allocation Model"),
            "model_formula":           weights.get("formula", ""),
        }
    }
