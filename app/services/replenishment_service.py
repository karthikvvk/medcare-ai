import math
from sqlalchemy.orm import Session
from datetime import date
from app.core.logging_config import logger
from app.models.database_models import SKU, DistributionCenter, Forecast, InventorySnapshot
from app.services.inventory_service import InventoryService
from app.core.config import settings

class ReplenishmentService:
    def __init__(self):
        self.inventory_service = InventoryService()

    def get_replenishment_recommendation(self, db: Session, sku_id: str, dc_id: str, current_date: date, service_level: float = None) -> dict:
        """
        Calculates the replenishment recommendation for a SKU at a DC.
        Applies min_order_qty rounding and DC capacity checks.
        """
        sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
        dc = db.query(DistributionCenter).filter(DistributionCenter.dc_id == dc_id).first()
        
        if not sku or not dc:
            return {}
            
        # Get inventory snapshot details
        inv_details = self.inventory_service.get_inventory_status(db, sku_id, dc_id, current_date, service_level)
        
        if not inv_details:
            return {}
            
        available_stock = inv_details["available_inventory"]
        incoming_stock = inv_details["incoming_inventory"]
        safety_stock = inv_details["safety_stock"]
        reorder_point = inv_details["reorder_point"]
        forecast_7d = inv_details["forecast_7d"]
        
        # Target Inventory = Forecasted Demand during review period (default 7 days) + safety stock
        target_inv = forecast_7d + safety_stock
        
        # Net requirements
        recommended_qty = target_inv - available_stock - incoming_stock
        recommended_qty = max(0.0, recommended_qty)
        
        # Apply Minimum Order Quantity (MOQ)
        if recommended_qty > 0:
            moq = sku.min_order_qty or 100
            if recommended_qty < moq:
                recommended_qty = float(moq)
            else:
                # Round up to nearest MOQ multiple
                recommended_qty = float(math.ceil(recommended_qty / moq) * moq)
                
        # Warehouse Capacity check
        # Calculate utilization of storage capacity across all SKUs in this DC
        # Get sum of closing_inventory + incoming_inventory for all SKUs in this DC
        total_dc_inventory = db.query(
            InventorySnapshot.closing_inventory + InventorySnapshot.incoming_inventory
        ).filter(
            InventorySnapshot.dc_id == dc_id,
            InventorySnapshot.date == current_date
        ).all()
        
        current_dc_utilization = sum(item[0] for item in total_dc_inventory)
        
        # Capacity cap
        available_capacity = max(0.0, dc.storage_capacity - current_dc_utilization)
        if recommended_qty > available_capacity:
            # Cap the recommendation to DC remaining capacity
            capped_qty = float(math.floor(available_capacity / 10) * 10) # round to nearest 10
            logger.warning(
                f"Replenishment capped by DC capacity limits for {sku_id} at {dc_id}. "
                f"Requested: {recommended_qty}, Capped to: {capped_qty}"
            )
            recommended_qty = capped_qty
            
        return {
            "sku_id": sku_id,
            "sku_name": sku.name,
            "dc_id": dc_id,
            "dc_name": dc.name,
            "available_inventory": available_stock,
            "incoming_inventory": incoming_stock,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "forecast_7d": forecast_7d,
            "target_inventory": round(target_inv, 2),
            "recommended_quantity": recommended_qty,
            "unit_cost": sku.unit_cost,
            "cost": round(recommended_qty * sku.unit_cost, 2),
            "lead_time_days": dc.lead_time_days,
            "criticality": sku.criticality
        }
