from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.core.logging_config import logger
from app.models.database_models import SKU, DistributionCenter, Batch, Transfer, Recommendation
from app.services.inventory_service import InventoryService
from app.services.expiry_service import ExpiryService
from app.core.config import settings
import uuid

class AllocationService:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.expiry_service = ExpiryService()

    def generate_transfer_recommendations(self, db: Session, current_date: date) -> list:
        """
        Scans all SKUs and DCs to find stock rebalancing opportunities.
        If DC A has excess (or near expiry excess) and DC B has shortage,
        recommends a transfer.
        """
        logger.info(f"Generating inter-DC transfer recommendations for date {current_date}...")
        
        skus = db.query(SKU).all()
        dcs = db.query(DistributionCenter).all()
        
        # Calculate inventory status for all SKU/DC combinations
        inv_statuses = {}
        for sku in skus:
            for dc in dcs:
                status = self.inventory_service.get_inventory_status(db, sku.sku_id, dc.dc_id, current_date)
                if status:
                    inv_statuses[(sku.sku_id, dc.dc_id)] = status

        # Fetch simulated expiry risks to identify batches that will waste if kept in place
        expiry_risks = self.expiry_service.simulate_fefo_expiry_risks(db, current_date)
        # Index expiry risks by (sku_id, dc_id, batch_id)
        expiry_risks_map = {(r["sku_id"], r["dc_id"], r["batch_id"]): r for r in expiry_risks}
        
        transfers_recommended = []
        
        # Define transfer parameters
        DEFAULT_TRANSIT_DAYS = 3
        MIN_TRANSFER_QTY = 50
        
        for sku in skus:
            sku_id = sku.sku_id
            
            # 1. Identify Shortage DCs for this SKU
            shortages = []
            for dc in dcs:
                status = inv_statuses.get((sku_id, dc.dc_id))
                if not status:
                    continue
                
                available_stock = status["available_inventory"]
                rop = status["reorder_point"]
                
                # We have a shortage if stock is below ROP
                if available_stock < rop:
                    shortage_qty = rop - available_stock
                    shortages.append({
                        "dc_id": dc.dc_id,
                        "dc_name": dc.name,
                        "qty_needed": shortage_qty,
                        "status_ref": status
                    })
                    
            # 2. Identify Surplus DCs / Near-Expiry Batches for this SKU
            surpluses = []
            
            # Fetch all active batches for this SKU
            active_batches = db.query(Batch).filter(
                Batch.sku_id == sku_id,
                Batch.remaining_quantity > 0
            ).all()
            
            for b in active_batches:
                # Find if this batch has expiry risk or excess
                status = inv_statuses.get((sku_id, b.dc_id))
                if not status:
                    continue
                
                # Check expiry risk details
                risk_info = expiry_risks_map.get((sku_id, b.dc_id, b.batch_id))
                simulated_waste = risk_info["simulated_waste"] if risk_info else 0.0
                
                # Days to expiry
                days_to_exp = (b.expiry_date - current_date).days
                
                # Available stock & target stock
                available_stock = status["available_inventory"]
                target_inv = status["forecast_7d"] + status["safety_stock"]
                
                # A surplus exists if there is projected waste in this batch, 
                # OR if the DC's available inventory exceeds target inventory.
                # In either case, we can transfer up to:
                # - remaining quantity of the batch
                # - available excess at the DC
                if simulated_waste > 0 or available_stock > target_inv:
                    excess_qty_at_dc = max(0.0, available_stock - target_inv)
                    # If batch is expiring soon, we prioritize transferring it even if it eats slightly into safety stock
                    # (since expiring stock will waste anyway)
                    usable_surplus = b.remaining_quantity
                    if simulated_waste == 0.0:
                        # If no expiry risk, only transfer what is truly excess
                        usable_surplus = min(b.remaining_quantity, excess_qty_at_dc)
                        
                    if usable_surplus >= MIN_TRANSFER_QTY:
                        surpluses.append({
                            "dc_id": b.dc_id,
                            "dc_name": status["dc_name"],
                            "batch": b,
                            "qty_available": usable_surplus,
                            "days_to_expiry": days_to_exp,
                            "has_expiry_risk": simulated_waste > 0
                        })
                        
            # Sort surpluses to transfer near-expiry items first
            surpluses.sort(key=lambda x: (not x["has_expiry_risk"], x["days_to_expiry"]))
            # Sort shortages to fulfill the most critical shortages first
            shortages.sort(key=lambda x: x["qty_needed"], reverse=True)
            
            # 3. Match shortages and surpluses
            for shortage in shortages:
                dest_dc_id = shortage["dc_id"]
                qty_needed = shortage["qty_needed"]
                
                for surplus in surpluses:
                    src_dc_id = surplus["dc_id"]
                    batch = surplus["batch"]
                    qty_avail = surplus["qty_available"]
                    days_to_exp = surplus["days_to_expiry"]
                    
                    if src_dc_id == dest_dc_id:
                        continue # Cannot transfer to self
                        
                    if qty_needed <= 0 or qty_avail <= 0:
                        continue
                        
                    # Check if transfer can arrive before expiry
                    # Transfer time is DEFAULT_TRANSIT_DAYS
                    if days_to_exp <= DEFAULT_TRANSIT_DAYS + 2:
                        # Expiry is too close for transport and use
                        continue
                        
                    # Calculate quantity to transfer
                    transfer_qty = min(qty_needed, qty_avail)
                    if transfer_qty < MIN_TRANSFER_QTY:
                        # If the matched quantity is too small, check if we can transfer MOQ
                        if qty_avail >= MIN_TRANSFER_QTY:
                            transfer_qty = MIN_TRANSFER_QTY
                        else:
                            continue
                            
                    # Register recommendation
                    rec_id = f"REC-TR-{uuid.uuid4().hex[:6].upper()}"
                    transfer_id = f"TR-{uuid.uuid4().hex[:6].upper()}"
                    
                    # Create recommendation details
                    reason = (
                        f"Inter-DC transfer recommended from {surplus['dc_name']} to {shortage['dc_name']}. "
                        f"Source DC has surplus stock of batch {batch.batch_id} expiring in {days_to_exp} days, "
                        f"while destination DC has stock shortage of {qty_needed:.0f} units below reorder point."
                    )
                    
                    rec_obj = Recommendation(
                        recommendation_id=rec_id,
                        sku_id=sku_id,
                        dc_id=dest_dc_id,
                        action_type="TRANSFER",
                        quantity=float(transfer_qty),
                        priority="HIGH" if surplus["has_expiry_risk"] else "MEDIUM",
                        reason=reason,
                        expected_impact=f"Avoids waste at {surplus['dc_name']} and resolves stock-out risk at {shortage['dc_name']}.",
                        confidence=0.90,
                        status="PENDING"
                    )
                    
                    tr_obj = Transfer(
                        transfer_id=transfer_id,
                        recommendation_id=rec_id,
                        sku_id=sku_id,
                        source_dc_id=src_dc_id,
                        destination_dc_id=dest_dc_id,
                        batch_id=batch.batch_id,
                        quantity=float(transfer_qty),
                        transit_days=DEFAULT_TRANSIT_DAYS,
                        status="RECOMMENDED"
                    )
                    
                    # Update simulated quantities for remaining steps
                    qty_needed -= transfer_qty
                    surplus["qty_available"] -= transfer_qty
                    
                    # Store objects
                    transfers_recommended.append({
                        "recommendation": rec_obj,
                        "transfer": tr_obj,
                        "sku_name": sku.name,
                        "source_dc_name": surplus["dc_name"],
                        "destination_dc_name": shortage["dc_name"],
                        "batch_id": batch.batch_id,
                        "days_to_expiry": days_to_exp
                    })
                    
        return transfers_recommended
