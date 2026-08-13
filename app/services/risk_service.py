from sqlalchemy.orm import Session
from datetime import date
from app.services.inventory_service import InventoryService
from app.models.database_models import SKU, DistributionCenter

class RiskService:
    def __init__(self):
        self.inventory_service = InventoryService()

    def evaluate_stockout_risk(self, db: Session, sku_id: str, dc_id: str, current_date: date, service_level: float = None) -> dict:
        """
        Evaluates the stockout risk of a specific SKU at a DC.
        Categorizes it into LOW, MEDIUM, HIGH, or CRITICAL.
        """
        inv_status = self.inventory_service.get_inventory_status(db, sku_id, dc_id, current_date, service_level)
        if not inv_status:
            return {"risk_level": "LOW", "risk_score": 0.0, "reason": "No stock record found."}
            
        available_inv = inv_status["available_inventory"]
        rop = inv_status["reorder_point"]
        doi = inv_status["days_of_inventory"]
        lead_time = inv_status["lead_time_days"]
        average_daily_demand = inv_status["average_daily_demand"]
        criticality = inv_status["criticality"]
        
        # Calculate risk scores (0 to 100)
        # CRITICAL: inventory runs out within lead time (DOI < Lead Time)
        if doi < lead_time:
            risk_level = "CRITICAL"
            # Scale score: higher score for lower inventory
            risk_score = 75.0 + (1.0 - (doi / (lead_time + 1e-5))) * 25.0
            reason = (
                f"Inventory is critically low at {available_inv:.0f} units (Days of Inventory = {doi:.1f} days). "
                f"With a lead time of {lead_time} days, a stock-out is expected before new shipments arrive."
            )
        elif available_inv < rop:
            risk_level = "HIGH"
            # Scale score: 50 to 75
            rop_ratio = available_inv / (rop + 1e-5)
            risk_score = 50.0 + (1.0 - rop_ratio) * 25.0
            reason = (
                f"Inventory of {available_inv:.0f} units has breached the reorder point of {rop:.0f} units. "
                f"Elevated risk of stock-out if demand surges."
            )
        elif available_inv < rop * 1.2:
            risk_level = "MEDIUM"
            # Scale score: 25 to 50
            risk_score = 25.0 + (1.0 - (available_inv / (rop * 1.2 + 1e-5))) * 25.0
            reason = (
                f"Inventory is approaching the reorder point. Current stock is {available_inv:.0f} units "
                f"against ROP of {rop:.0f} units."
            )
        else:
            risk_level = "LOW"
            risk_score = max(0.0, 25.0 * (1.0 - (doi / 45.0))) # low risk scales down if DOI is very large
            reason = f"Inventory is healthy at {available_inv:.0f} units (Days of Inventory = {doi:.1f} days)."

        # Elevate priority/score for critical medications
        if criticality == "CRITICAL" and risk_level in ["MEDIUM", "HIGH"]:
            if risk_level == "MEDIUM":
                risk_level = "HIGH"
                risk_score += 10.0
            elif risk_level == "HIGH":
                risk_level = "CRITICAL"
                risk_score += 10.0
            reason += " [MEDICINE IS CRITICAL]"

        return {
            "sku_id": sku_id,
            "sku_name": inv_status["sku_name"],
            "dc_id": dc_id,
            "dc_name": inv_status["dc_name"],
            "available_inventory": available_inv,
            "days_of_inventory": doi,
            "lead_time_days": lead_time,
            "reorder_point": rop,
            "risk_level": risk_level,
            "risk_score": round(min(100.0, risk_score), 2),
            "reason": reason
        }
