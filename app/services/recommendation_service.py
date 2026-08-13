from sqlalchemy.orm import Session
from datetime import date, datetime
from app.core.logging_config import logger
from app.models.database_models import SKU, DistributionCenter, Recommendation, Transfer, Forecast
from app.services.inventory_service import InventoryService
from app.services.replenishment_service import ReplenishmentService
from app.services.allocation_service import AllocationService
from app.services.risk_service import RiskService
from app.services.explanation_service import ExplanationService
from app.services.expiry_service import ExpiryService
import uuid

class RecommendationService:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.replenishment_service = ReplenishmentService()
        self.allocation_service = AllocationService()
        self.risk_service = RiskService()
        self.expiry_service = ExpiryService()
        self.explanation_service = ExplanationService()

    def generate_recommendations(self, db: Session, current_date: date, service_level: float = None) -> list:
        """
        Orchestrates demand sensing, risk analysis, replenishment planning,
        inter-DC allocation, and escalation leveling.
        Saves all generated recommendations and transfers to the database.
        """
        logger.info(f"Generating action recommendations for date {current_date}...")
        
        # Clear existing recommendations/transfers for the current date
        # Note: In a production system, we might update or archive, but for hackathon demo we clear and regenerate.
        db.query(Transfer).delete()
        db.query(Recommendation).delete()
        db.commit()

        skus = db.query(SKU).all()
        dcs = db.query(DistributionCenter).all()
        
        recs_to_save = []
        transfers_to_save = []
        
        # 1. First, generate Inter-DC Transfers (to rebalance stock before placing new orders)
        transfer_ops = self.allocation_service.generate_transfer_recommendations(db, current_date)
        
        # Track simulated stock adjustments from transfers to avoid double ordering
        # key: (sku_id, dc_id), val: adjusted_incoming_qty
        transfer_adjustments = {}
        
        for op in transfer_ops:
            rec = op["recommendation"]
            transfer = op["transfer"]
            
            # Save objects
            recs_to_save.append(rec)
            transfers_to_save.append(transfer)
            
            # Register incoming stock adjustment at destination
            dest_key = (rec.sku_id, rec.dc_id)
            transfer_adjustments[dest_key] = transfer_adjustments.get(dest_key, 0.0) + rec.quantity
            
            # Register outgoing stock adjustment at source
            src_key = (rec.sku_id, transfer.source_dc_id)
            transfer_adjustments[src_key] = transfer_adjustments.get(src_key, 0.0) - rec.quantity

        # 2. Next, generate Replenishment orders from suppliers
        for sku in skus:
            for dc in dcs:
                sku_id = sku.sku_id
                dc_id = dc.dc_id
                key = (sku_id, dc_id)
                
                # Fetch replenishment recommendation
                repl_rec = self.replenishment_service.get_replenishment_recommendation(db, sku_id, dc_id, current_date, service_level)
                if not repl_rec:
                    continue
                    
                recommended_qty = repl_rec["recommended_quantity"]
                
                # Subtract any incoming transfer quantities that will arrive at this DC
                adjusted_qty = recommended_qty - transfer_adjustments.get(key, 0.0)
                adjusted_qty = max(0.0, adjusted_qty)
                
                # Check stock-out risk level to determine Priority / Escalation
                risk_info = self.risk_service.evaluate_stockout_risk(db, sku_id, dc_id, current_date, service_level)
                risk_level = risk_info["risk_level"]
                risk_score = risk_info["risk_score"]
                
                action_type = "NO_ACTION"
                priority = "LOW"
                expected_impact = "No action required. Inventory is healthy."
                
                # Escalation logic
                if adjusted_qty > 0:
                    action_type = "REPLENISH"
                    if risk_level == "CRITICAL":
                        priority = "CRITICAL"
                        expected_impact = "Prevent an imminent stock-out of a critical medication."
                    elif risk_level == "HIGH":
                        priority = "HIGH"
                        expected_impact = "Replenish stock to avoid safety stock breach."
                    elif risk_level == "MEDIUM":
                        priority = "MEDIUM"
                        expected_impact = "Reorder stock according to lead times."
                    else:
                        priority = "LOW"
                        expected_impact = "Standard inventory reorder."
                elif risk_level in ["HIGH", "CRITICAL"]:
                    # Stock is low, but no replenishment quantity recommended (perhaps capacity or incoming shipment covers it)
                    action_type = "MONITOR"
                    priority = "HIGH" if risk_level == "CRITICAL" else "MEDIUM"
                    expected_impact = "Monitor stock level and incoming shipments."
                
                # Build explanation context
                explanation_ctx = {
                    "sku_id": sku_id,
                    "lead_time_days": dc.lead_time_days,
                    "available_inventory": repl_rec["available_inventory"],
                    "reorder_point": repl_rec["reorder_point"],
                    "forecast_7d": repl_rec["forecast_7d"]
                }
                
                # Create human-readable explanation
                explanation = self.explanation_service.get_deterministic_explanation(
                    action_type, sku.name, dc.name, adjusted_qty, explanation_ctx
                )
                
                if action_type != "NO_ACTION" or risk_level != "LOW":
                    rec_id = f"REC-RP-{uuid.uuid4().hex[:6].upper()}"
                    rec_obj = Recommendation(
                        recommendation_id=rec_id,
                        sku_id=sku_id,
                        dc_id=dc_id,
                        action_type=action_type,
                        quantity=float(adjusted_qty),
                        priority=priority,
                        reason=explanation,
                        expected_impact=expected_impact,
                        confidence=round(0.95 - (sku.demand_variability * 0.2), 2),
                        status="PENDING"
                    )
                    recs_to_save.append(rec_obj)
                    
        # 3. Expiry Check - Flag near-expiry monitor actions
        # If a batch has critical expiry risk but was not flagged under transfers, add a MONITOR/REDUCE_ORDER alert
        expiry_reports = self.expiry_service.simulate_fefo_expiry_risks(db, current_date)
        for rep in expiry_reports:
            if rep["risk_level"] in ["CRITICAL", "HIGH"]:
                # Check if we already have an action for this SKU/DC
                sku_id = rep["sku_id"]
                dc_id = rep["dc_id"]
                
                existing = [r for r in recs_to_save if r.sku_id == sku_id and r.dc_id == dc_id]
                if not existing:
                    # Create custom warning recommendation
                    rec_id = f"REC-EX-{uuid.uuid4().hex[:6].upper()}"
                    reason = (
                        f"Critical expiry warning for batch {rep['batch_id']}. "
                        f"Batch contains {rep['remaining_quantity']:.0f} units expiring on {rep['expiry_date']} "
                        f"({rep['days_to_expiry']} days remaining). Projections indicate {rep['simulated_waste']:.0f} units "
                        f"will waste due to low demand at {rep['dc_name']}."
                    )
                    
                    rec_obj = Recommendation(
                        recommendation_id=rec_id,
                        sku_id=sku_id,
                        dc_id=dc_id,
                        action_type="REDUCE_ORDER" if rep["days_to_expiry"] > 14 else "MONITOR",
                        quantity=float(rep["simulated_waste"]),
                        priority=rep["risk_level"],
                        reason=reason,
                        expected_impact="Minimize expiry-driven financial loss and product wastage.",
                        confidence=0.98,
                        status="PENDING"
                    )
                    recs_to_save.append(rec_obj)

        # Save everything to the database
        db.bulk_save_objects(recs_to_save)
        # Separate table save for transfers since they contain complex link ids
        db.bulk_save_objects(transfers_to_save)
        db.commit()
        
        logger.info(f"Generated and stored {len(recs_to_save)} action recommendations in database.")
        return recs_to_save
