import numpy as np
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.models.database_models import Batch, SKU, DistributionCenter
from app.services.inventory_service import InventoryService
from app.core.config import settings

class ExpiryService:
    def __init__(self):
        self.inventory_service = InventoryService()

    def simulate_fefo_expiry_risks(self, db: Session, current_date: date) -> list:
        """
        Simulates future demand consumption using FEFO logic to identify batch-level expiry risk.
        Returns a list of batch risk reports.
        """
        # Fetch all active batches (remaining quantity > 0)
        batches = db.query(Batch).filter(Batch.remaining_quantity > 0).all()
        
        # Group by SKU + DC
        sku_dc_batches = {}
        for b in batches:
            key = (b.sku_id, b.dc_id)
            if key not in sku_dc_batches:
                sku_dc_batches[key] = []
            sku_dc_batches[key].append(b)
            
        risk_reports = []
        
        for (sku_id, dc_id), b_list in sku_dc_batches.items():
            sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
            dc = db.query(DistributionCenter).filter(DistributionCenter.dc_id == dc_id).first()
            if not sku or not dc:
                continue
                
            # Sort batches by expiry date (FEFO)
            b_list.sort(key=lambda x: x.expiry_date)
            
            # Get Average Daily Demand (ADD)
            add = self.inventory_service.get_average_daily_demand(db, sku_id, dc_id, current_date)
            
            # We simulate daily consumption up to the maximum expiry date in the list
            max_expiry_date = b_list[-1].expiry_date
            sim_days = (max_expiry_date - current_date).days
            
            if sim_days <= 0:
                # All batches are already expired!
                for b in b_list:
                    days_to_exp = (b.expiry_date - current_date).days
                    risk_reports.append({
                        "batch_id": b.batch_id,
                        "sku_id": sku_id,
                        "sku_name": sku.name,
                        "dc_id": dc_id,
                        "dc_name": dc.name,
                        "unit_cost": sku.unit_cost,
                        "remaining_quantity": b.remaining_quantity,
                        "expiry_date": b.expiry_date,
                        "days_to_expiry": days_to_exp,
                        "simulated_waste": b.remaining_quantity,
                        "risk_score": 100.0,
                        "risk_level": "CRITICAL",
                        "reason": f"Batch expired on {b.expiry_date}."
                    })
                continue
                
            # Create mutable quantities for simulation
            sim_batches = [{
                "batch": b,
                "qty": b.remaining_quantity,
                "exp_days": (b.expiry_date - current_date).days
            } for b in b_list]
            
            # Run simulation day by day
            for day in range(1, sim_days + 1):
                # Demand for today
                daily_demand = add
                
                # Consume demand using FEFO from active batches that haven't expired
                for sb in sim_batches:
                    if daily_demand <= 0:
                        break
                    # If this batch is not expired yet on this simulation day
                    if sb["exp_days"] >= day and sb["qty"] > 0:
                        consume = min(sb["qty"], daily_demand)
                        sb["qty"] -= consume
                        daily_demand -= consume
                        
            # Analyze results of simulation
            for sb in sim_batches:
                b = sb["batch"]
                remaining_qty_sim = sb["qty"]
                days_to_exp = sb["exp_days"]
                
                # Expiry status
                if days_to_exp < 0:
                    risk_level = "CRITICAL"
                    risk_score = 100.0
                    reason = f"Batch expired {abs(days_to_exp)} days ago."
                else:
                    # Risk score based on wastage fraction and time remaining
                    waste_fraction = remaining_qty_sim / b.remaining_quantity if b.remaining_quantity > 0 else 0.0
                    
                    if remaining_qty_sim == 0:
                        risk_level = "SAFE"
                        risk_score = 0.0
                        reason = "Entire batch is projected to be consumed before expiry."
                    elif days_to_exp <= settings.EXPIRY_EXTREME_DAYS:
                        risk_level = "CRITICAL"
                        risk_score = 95.0
                        reason = f"Expires in {days_to_exp} days. Simulated wastage of {remaining_qty_sim:.0f} units."
                    elif days_to_exp <= settings.EXPIRY_CRITICAL_DAYS:
                        risk_level = "CRITICAL" if waste_fraction > 0.5 else "HIGH"
                        risk_score = 80.0 if risk_level == "CRITICAL" else 65.0
                        reason = f"Expires in {days_to_exp} days. Projections show {remaining_qty_sim:.0f} units will waste."
                    elif days_to_exp <= settings.EXPIRY_WARNING_DAYS:
                        risk_level = "HIGH" if waste_fraction > 0.2 else "WATCH"
                        risk_score = 50.0 if risk_level == "HIGH" else 30.0
                        reason = f"Expires in {days_to_exp} days. Projections show {remaining_qty_sim:.0f} units will waste."
                    else:
                        # Beyond warning window but has wastage
                        risk_level = "WATCH" if remaining_qty_sim > 50 else "SAFE"
                        risk_score = 15.0 if risk_level == "WATCH" else 5.0
                        reason = f"Expires in {days_to_exp} days. Long term risk of {remaining_qty_sim:.0f} units waste."
                        
                risk_reports.append({
                    "batch_id": b.batch_id,
                    "sku_id": sku_id,
                    "sku_name": sku.name,
                    "dc_id": dc_id,
                    "dc_name": dc.name,
                    "unit_cost": sku.unit_cost,
                    "remaining_quantity": b.remaining_quantity,
                    "expiry_date": b.expiry_date,
                    "days_to_expiry": days_to_exp,
                    "simulated_waste": round(remaining_qty_sim, 2),
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "reason": reason
                })
                
        return risk_reports
