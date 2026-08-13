"""
Expiry Prediction Service
=========================
Implements the Expiry Aware Allocation Model (Weighted Risk Scoring)
from expiry_related_programs_temp_dir/expiry_risk.py and expiry_model_weights.json.

Formula:
    expiry_risk_score = 0.40 * expiry_urgency_score
                      + 0.35 * inventory_pressure_score
                      + 0.25 * coverage_risk_score
"""

import json
import os
import numpy as np
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.models.database_models import Batch, SKU, DistributionCenter, DemandHistory, Forecast

# ---------------------------------------------------------------------------
# Load model weights
# ---------------------------------------------------------------------------

_WEIGHTS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../expiry_related_programs_temp_dir/expiry_model_weights.json"
)

def _load_weights() -> dict:
    try:
        with open(_WEIGHTS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load expiry_model_weights.json: {e}. Using defaults.")
        return {
            "weights": {
                "expiry_urgency_score": 0.40,
                "inventory_pressure_score": 0.35,
                "coverage_risk_score": 0.25,
            }
        }

_MODEL_WEIGHTS = _load_weights()
_W = _MODEL_WEIGHTS["weights"]


# ---------------------------------------------------------------------------
# Score helpers (directly ported from expiry_risk.py)
# ---------------------------------------------------------------------------

def _expiry_urgency_score(days: float) -> float:
    if days < 0:      return 1.00
    elif days <= 7:   return 1.00
    elif days <= 14:  return 0.95
    elif days <= 30:  return 0.85
    elif days <= 60:  return 0.70
    elif days <= 90:  return 0.50
    elif days <= 180: return 0.30
    elif days <= 365: return 0.15
    else:             return 0.05


def _inventory_pressure_score(ratio: float) -> float:
    if ratio >= 12:   return 1.00
    elif ratio >= 8:  return 0.90
    elif ratio >= 6:  return 0.80
    elif ratio >= 4:  return 0.65
    elif ratio >= 2:  return 0.40
    elif ratio >= 1:  return 0.20
    else:             return 0.05


def _coverage_risk_score(ratio: float) -> float:
    if ratio >= 1:      return 1.00
    elif ratio >= 0.75: return 0.80
    elif ratio >= 0.50: return 0.60
    elif ratio >= 0.25: return 0.30
    else:               return 0.05


def _classify(score: float, days: float, expected_remaining: float) -> str:
    if days < 0:                          return "CRITICAL"
    if days <= 30 and expected_remaining > 0: return "CRITICAL"
    if score >= 0.75:                     return "HIGH"
    if score >= 0.45:                     return "WATCH"
    return "LOW"


def _recommended_action(risk: str, days: float) -> str:
    if days < 0:          return "EXPIRED_STOCK"
    if risk == "CRITICAL": return "URGENT_ALLOCATION"
    if risk == "HIGH":    return "PRIORITIZE_ALLOCATION"
    if risk == "WATCH":   return "MONITOR_AND_PLAN"
    return "NORMAL_ALLOCATION"


# ---------------------------------------------------------------------------
# Per-tier AI suggestion builder
# ---------------------------------------------------------------------------

def _build_suggestions(items: list, tier: str, today: date) -> dict:
    """
    Returns a structured suggestion dict with:
      - status : one-line risk summary
      - steps  : ordered list of action steps (rendered as flow diagram)
    """
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
# Main service
# ---------------------------------------------------------------------------

class ExpiryPredictionService:
    """
    Runs the Expiry Aware Allocation Model on all active batches and
    returns structured prediction output for the Expiry Management page.
    """

    def _get_weekly_demand(self, db: Session, sku_id: str, dc_id: str, today: date) -> float:
        """
        Returns expected weekly demand for a SKU+DC.
        Priority: latest 7-day forecast → 14-day historical avg → SKU base demand.
        """
        # Try 7-day forecast
        fc = db.query(Forecast).filter(
            Forecast.sku_id == sku_id,
            Forecast.dc_id == dc_id,
            Forecast.horizon_days == 7,
            Forecast.prediction_date == today
        ).first()
        if fc and fc.forecasted_demand > 0:
            return float(fc.forecasted_demand)

        # Historical 14-day rolling average (×7 to get weekly)
        from sqlalchemy import func
        start = today - timedelta(days=14)
        avg = db.query(func.avg(DemandHistory.quantity)).filter(
            DemandHistory.sku_id == sku_id,
            DemandHistory.dc_id == dc_id,
            DemandHistory.date >= start,
            DemandHistory.date <= today
        ).scalar()
        if avg is not None:
            return float(avg) * 7.0

        # SKU base demand fallback
        sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
        return float(sku.base_demand) * 7.0 if sku else 10.0

    def run_expiry_model(self, db: Session, current_date: date) -> dict:
        """
        Runs the full expiry prediction pipeline and returns a structured
        response suitable for the Expiry Management API endpoint.

        Returns:
            {
                "warehouses_at_risk": [...],    # per-DC risk summary cards
                "critical_items": [...],
                "high_items": [...],
                "watch_items": [...],
                "low_items": [...],
                "suggestions_critical": str,
                "suggestions_high": str,
                "suggestions_watch": str,
                "model_info": {...}
            }
        """
        logger.info(f"Running ExpiryPredictionService for date={current_date}")

        # Fetch all active batches
        batches = db.query(Batch).filter(Batch.remaining_quantity > 0).all()
        if not batches:
            logger.warning("No active batches found for expiry prediction.")
            return _empty_response()

        # Cache SKU and DC lookups
        sku_cache: dict = {}
        dc_cache: dict = {}

        predictions = []

        for b in batches:
            sku_id = b.sku_id
            dc_id = b.dc_id

            if sku_id not in sku_cache:
                sku_cache[sku_id] = db.query(SKU).filter(SKU.sku_id == sku_id).first()
            if dc_id not in dc_cache:
                dc_cache[dc_id] = db.query(DistributionCenter).filter(DistributionCenter.dc_id == dc_id).first()

            sku = sku_cache[sku_id]
            dc = dc_cache[dc_id]
            if not sku or not dc:
                continue

            # ── Feature Engineering ─────────────────────────────────────────
            days_to_expiry = (b.expiry_date - current_date).days
            weeks_to_expiry = days_to_expiry / 7.0

            available_qty = max(0.0, float(b.remaining_quantity))

            weekly_demand = self._get_weekly_demand(db, sku_id, dc_id, current_date)

            expected_demand_before_expiry = weekly_demand * max(0.0, weeks_to_expiry)
            expected_remaining_stock = max(0.0, available_qty - expected_demand_before_expiry)
            expected_writeoff_ratio = (
                expected_remaining_stock / available_qty if available_qty > 0 else 0.0
            )
            expected_writeoff_ratio = min(1.0, max(0.0, expected_writeoff_ratio))

            inventory_coverage_weeks = (
                available_qty / weekly_demand if weekly_demand > 0 else 999.0
            )
            coverage_vs_expiry_ratio = (
                inventory_coverage_weeks / weeks_to_expiry if weeks_to_expiry > 0 else 999.0
            )
            inventory_pressure_ratio = (
                available_qty / weekly_demand if weekly_demand > 0 else 0.0
            )

            # ── Intermediate Scores ──────────────────────────────────────────
            urg_score  = _expiry_urgency_score(days_to_expiry)
            pres_score = _inventory_pressure_score(inventory_pressure_ratio)
            cov_score  = _coverage_risk_score(coverage_vs_expiry_ratio)

            # ── Final Weighted Score ─────────────────────────────────────────
            risk_score = (
                _W["expiry_urgency_score"]      * urg_score
                + _W["inventory_pressure_score"] * pres_score
                + _W["coverage_risk_score"]      * cov_score
            )

            # Force expired stock to max risk
            if days_to_expiry < 0:
                risk_score = 1.0

            risk_score = float(np.clip(risk_score, 0.0, 1.0))

            # ── Classification ───────────────────────────────────────────────
            risk_class = _classify(risk_score, days_to_expiry, expected_remaining_stock)
            action = _recommended_action(risk_class, days_to_expiry)

            # ── Write-off Quantity ───────────────────────────────────────────
            expected_writeoff_qty = int(min(
                round(available_qty * expected_writeoff_ratio),
                available_qty
            ))

            predictions.append({
                "batch_id": b.batch_id,
                "sku_id": sku_id,
                "sku_name": sku.name,
                "dc_id": dc_id,
                "dc_name": dc.name,
                "dc_location": dc.location,
                "manufacturing_date": str(b.manufacturing_date),
                "expiry_date": str(b.expiry_date),
                "days_to_expiry": days_to_expiry,
                "weeks_to_expiry": round(weeks_to_expiry, 2),
                "available_quantity": int(available_qty),
                "expected_weekly_demand": round(weekly_demand, 2),
                "expected_demand_before_expiry": round(expected_demand_before_expiry, 2),
                "expected_remaining_stock": round(expected_remaining_stock, 2),
                "inventory_coverage_weeks": round(inventory_coverage_weeks, 2),
                "expiry_urgency_score": round(urg_score, 4),
                "inventory_pressure_score": round(pres_score, 4),
                "coverage_risk_score": round(cov_score, 4),
                "expiry_risk_score": round(risk_score, 4),
                "expected_writeoff_quantity": expected_writeoff_qty,
                "expiry_risk": risk_class,
                "recommended_action": action,
                "unit_cost": float(sku.unit_cost),
                "projected_loss_inr": round(expected_writeoff_qty * sku.unit_cost, 2),
            })

        # ── Sort: by risk score descending ───────────────────────────────────
        predictions.sort(key=lambda x: -x["expiry_risk_score"])

        # ── Tier separation ──────────────────────────────────────────────────
        critical_items = [p for p in predictions if p["expiry_risk"] == "CRITICAL"]
        high_items     = [p for p in predictions if p["expiry_risk"] == "HIGH"]
        watch_items    = [p for p in predictions if p["expiry_risk"] == "WATCH"]
        low_items      = [p for p in predictions if p["expiry_risk"] == "LOW"]

        # ── Warehouses at Risk ───────────────────────────────────────────────
        warehouses_at_risk = _build_warehouse_cards(predictions, dc_cache)

        # ── AI Suggestions ───────────────────────────────────────────────────
        suggestions_critical = _build_suggestions(critical_items, "CRITICAL", current_date)
        suggestions_high     = _build_suggestions(high_items,     "HIGH",     current_date)
        suggestions_watch    = _build_suggestions(watch_items,    "WATCH",    current_date)

        logger.info(
            f"ExpiryPredictionService complete: "
            f"CRITICAL={len(critical_items)}, HIGH={len(high_items)}, "
            f"WATCH={len(watch_items)}, LOW={len(low_items)}"
        )

        return {
            "warehouses_at_risk": warehouses_at_risk,
            "critical_items": critical_items,
            "high_items": high_items,
            "watch_items": watch_items,
            "low_items": low_items,
            "suggestions_critical": suggestions_critical,
            "suggestions_high": suggestions_high,
            "suggestions_watch": suggestions_watch,
            "summary": {
                "total_batches": len(predictions),
                "critical_count": len(critical_items),
                "high_count": len(high_items),
                "watch_count": len(watch_items),
                "low_count": len(low_items),
                "total_at_risk_units": sum(p["expected_writeoff_quantity"] for p in predictions),
                "total_projected_loss_inr": round(sum(p["projected_loss_inr"] for p in predictions), 2),
                "model_name": _MODEL_WEIGHTS.get("model_name", "Expiry Aware Allocation Model"),
                "model_formula": _MODEL_WEIGHTS.get("formula", ""),
            }
        }


def _build_warehouse_cards(predictions: list, dc_cache: dict) -> list:
    """
    Aggregates per-batch predictions into per-DC warehouse risk summary cards.
    """
    dc_map: dict = {}
    for p in predictions:
        dc_id = p["dc_id"]
        if dc_id not in dc_map:
            dc_map[dc_id] = {
                "dc_id": dc_id,
                "dc_name": p["dc_name"],
                "dc_location": p["dc_location"],
                "total_batches": 0,
                "critical_batches": 0,
                "high_batches": 0,
                "watch_batches": 0,
                "low_batches": 0,
                "total_at_risk_units": 0,
                "total_projected_loss_inr": 0.0,
                "worst_risk_score": 0.0,
                "worst_risk_level": "LOW",
                "skus_affected": set(),
            }
        d = dc_map[dc_id]
        d["total_batches"] += 1
        d["skus_affected"].add(p["sku_id"])
        d["total_at_risk_units"] += p["expected_writeoff_quantity"]
        d["total_projected_loss_inr"] += p["projected_loss_inr"]
        if p["expiry_risk_score"] > d["worst_risk_score"]:
            d["worst_risk_score"] = p["expiry_risk_score"]
            d["worst_risk_level"] = p["expiry_risk"]
        d[f"{p['expiry_risk'].lower()}_batches"] += 1

    result = []
    for dc_id, d in dc_map.items():
        # Only surface warehouses that have at least one non-LOW batch
        if d["worst_risk_level"] == "LOW" and d["critical_batches"] == 0 and d["high_batches"] == 0 and d["watch_batches"] == 0:
            # Still include it but mark as safe
            pass
        result.append({
            "dc_id": d["dc_id"],
            "dc_name": d["dc_name"],
            "dc_location": d["dc_location"],
            "total_batches": d["total_batches"],
            "critical_batches": d["critical_batches"],
            "high_batches": d["high_batches"],
            "watch_batches": d["watch_batches"],
            "low_batches": d["low_batches"],
            "skus_affected": len(d["skus_affected"]),
            "total_at_risk_units": d["total_at_risk_units"],
            "total_projected_loss_inr": round(d["total_projected_loss_inr"], 2),
            "worst_risk_score": round(d["worst_risk_score"], 4),
            "worst_risk_level": d["worst_risk_level"],
        })

    # Sort warehouses: worst first
    _order = {"CRITICAL": 0, "HIGH": 1, "WATCH": 2, "LOW": 3}
    result.sort(key=lambda x: (_order.get(x["worst_risk_level"], 4), -x["worst_risk_score"]))
    return result


def _empty_response() -> dict:
    return {
        "warehouses_at_risk": [],
        "critical_items": [],
        "high_items": [],
        "watch_items": [],
        "low_items": [],
        "suggestions_critical": "No active batches found in the system.",
        "suggestions_high": "No active batches found in the system.",
        "suggestions_watch": "No active batches found in the system.",
        "summary": {
            "total_batches": 0,
            "critical_count": 0,
            "high_count": 0,
            "watch_count": 0,
            "low_count": 0,
            "total_at_risk_units": 0,
            "total_projected_loss_inr": 0.0,
            "model_name": "Expiry Aware Allocation Model",
            "model_formula": "",
        }
    }
