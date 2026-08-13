from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
from app.core.database import get_db
from app.models.database_models import Recommendation, Transfer, SKU, DistributionCenter
from app.models.schemas import RecommendationResponse, TransferResponse, SimulationRequest, SimulationResponse, SimulationResultSummary
from app.services.recommendation_service import RecommendationService
from app.services.inventory_service import InventoryService
from app.services.risk_service import RiskService
from app.services.expiry_service import ExpiryService
import math

router = APIRouter(prefix="/recommendations", tags=["Recommendations & Simulation"])
rec_service = RecommendationService()
inventory_service = InventoryService()
risk_service = RiskService()
expiry_service = ExpiryService()

@router.get("", response_model=List[RecommendationResponse])
def get_recommendations(
    date_str: str = Query(..., description="Evaluation date (YYYY-MM-DD)"),
    regenerate: bool = Query(False, description="Force re-generation of recommendations"),
    db: Session = Depends(get_db)
):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    if regenerate:
        rec_service.generate_recommendations(db, current_date)
        
    recs = db.query(Recommendation).all()
    # If DB is empty, run recommendation engine once
    if not recs:
        recs = rec_service.generate_recommendations(db, current_date)
        
    return recs

@router.get("/transfers", response_model=List[TransferResponse])
def get_transfers(db: Session = Depends(get_db)):
    return db.query(Transfer).all()

@router.post("/simulate", response_model=SimulationResponse)
def run_simulation(
    req: SimulationRequest,
    date_str: str = Query(..., description="Target evaluation date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    skus = db.query(SKU).all()
    dcs = db.query(DistributionCenter).all()
    
    details = []
    
    original_stockouts = 0
    simulated_stockouts = 0
    original_expiry_risks = 0
    simulated_expiry_risks = 0
    additional_replenishment_units = 0.0
    
    # Pre-simulate expiry reports to compare
    expiry_reports = expiry_service.simulate_fefo_expiry_risks(db, current_date)
    expiry_map = {(r["sku_id"], r["dc_id"]): r["risk_level"] for r in expiry_reports}
    
    for sku in skus:
        sku_id = sku.sku_id
        for dc in dcs:
            dc_id = dc.dc_id
            
            # 1. Fetch original status
            orig_status = inventory_service.get_inventory_status(db, sku_id, dc_id, current_date)
            if not orig_status:
                continue
                
            orig_risk_info = risk_service.evaluate_stockout_risk(db, sku_id, dc_id, current_date)
            orig_risk = orig_risk_info["risk_level"]
            
            if orig_risk in ["HIGH", "CRITICAL"]:
                original_stockouts += 1
                
            # Original replenishment qty
            repl_rec_orig = rec_service.replenishment_service.get_replenishment_recommendation(db, sku_id, dc_id, current_date)
            orig_replenish_qty = repl_rec_orig.get("recommended_quantity", 0.0) if repl_rec_orig else 0.0
            
            # Original expiry risk
            orig_expiry_risk = expiry_map.get((sku_id, dc_id), "SAFE")
            if orig_expiry_risk in ["HIGH", "CRITICAL"]:
                original_expiry_risks += 1

            # 2. Compute SIMULATED shifts
            # Apply shifts
            demand_multiplier = (1.0 + req.demand_increase_pct / 100.0) * (1.0 + req.promotion_impact_pct / 100.0) * req.seasonality_multiplier
            
            sim_add = orig_status["average_daily_demand"] * demand_multiplier
            sim_forecast_7d = orig_status["forecast_7d"] * demand_multiplier
            
            sim_lead_time = max(1, orig_status["lead_time_days"] + req.supplier_lead_time_days_offset)
            sim_available_stock = orig_status["available_inventory"] * (1.0 - req.inventory_reduction_pct / 100.0)
            
            # Recalculate safety stock
            std_demand = inventory_service.get_demand_std(db, sku_id, dc_id, current_date)
            # Standard z-score
            sim_ss = 1.96 * std_demand * math.sqrt(sim_lead_time)
            
            # Recalculate ROP
            sim_rop = (sim_add * sim_lead_time) + sim_ss
            
            # Recalculate Days of Inventory
            sim_doi = sim_available_stock / sim_add if sim_add > 0 else 999.0
            
            # Determine simulated stockout risk
            if sim_doi < sim_lead_time:
                sim_risk = "CRITICAL"
            elif sim_available_stock < sim_rop:
                sim_risk = "HIGH"
            elif sim_available_stock < sim_rop * 1.2:
                sim_risk = "MEDIUM"
            else:
                sim_risk = "LOW"
                
            if sim_risk in ["HIGH", "CRITICAL"]:
                simulated_stockouts += 1
                
            # Recalculate replenishment qty
            sim_target_inv = sim_forecast_7d + sim_ss
            sim_replenish_qty = sim_target_inv - sim_available_stock
            sim_replenish_qty = max(0.0, sim_replenish_qty)
            
            if sim_replenish_qty > 0:
                moq = sku.min_order_qty or 100
                if sim_replenish_qty < moq:
                    sim_replenish_qty = float(moq)
                else:
                    sim_replenish_qty = float(math.ceil(sim_replenish_qty / moq) * moq)
                    
            # Check warehouse cap
            if sim_replenish_qty + sim_available_stock > dc.storage_capacity:
                sim_replenish_qty = max(0.0, float(math.floor((dc.storage_capacity - sim_available_stock) / 10) * 10))

            additional_replenishment_units += max(0.0, sim_replenish_qty - orig_replenish_qty)

            # Simulated Expiry Risk (higher demand reduces expiry risk, lower demand raises it)
            # If simulated demand is 40% higher, remaining shelf life is consumed faster
            sim_expiry_risk = orig_expiry_risk
            if demand_multiplier > 1.2 and orig_expiry_risk in ["HIGH", "CRITICAL"]:
                sim_expiry_risk = "WATCH" if orig_expiry_risk == "HIGH" else "HIGH"
            elif demand_multiplier < 0.8 and orig_expiry_risk == "WATCH":
                sim_expiry_risk = "HIGH"
                
            if sim_expiry_risk in ["HIGH", "CRITICAL"]:
                simulated_expiry_risks += 1
                
            # Reasons for differences
            reason_parts = []
            if sim_risk != orig_risk:
                reason_parts.append(f"Stockout risk shifted from {orig_risk} to {sim_risk}")
            if sim_replenish_qty != orig_replenish_qty:
                reason_parts.append(f"Replenishment quantity changed by {sim_replenish_qty - orig_replenish_qty:.0f} units")
            if sim_expiry_risk != orig_expiry_risk:
                reason_parts.append(f"Expiry risk shifted from {orig_expiry_risk} to {sim_expiry_risk}")
                
            reason = ", ".join(reason_parts) if reason_parts else "No significant changes."
            
            details.append(SimulationResultSummary(
                sku_id=sku_id,
                dc_id=dc_id,
                original_stockout_risk=orig_risk,
                simulated_stockout_risk=sim_risk,
                original_replenish_qty=float(orig_replenish_qty),
                simulated_replenish_qty=float(sim_replenish_qty),
                original_expiry_risk=orig_expiry_risk,
                simulated_expiry_risk=sim_expiry_risk,
                reason=reason
            ))
            
    return SimulationResponse(
        original_stockout_events=original_stockouts,
        simulated_stockout_events=simulated_stockouts,
        original_expiry_risks=original_expiry_risks,
        simulated_expiry_risks=simulated_expiry_risks,
        additional_replenishment_units=additional_replenishment_units,
        details=details
    )

@router.post("/{rec_id}/status")
def update_recommendation_status(
    rec_id: str,
    status: str = Query(..., description="APPROVED or REJECTED"),
    db: Session = Depends(get_db)
):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if status not in ["APPROVED", "REJECTED", "PENDING"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
    rec.status = status
    db.commit()
    return {"message": f"Recommendation {rec_id} status updated to {status}", "status": rec.status}
