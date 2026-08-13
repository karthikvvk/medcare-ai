import sys
import os
import argparse
from datetime import datetime, date, timedelta

# Adjust path to enable importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging_config import logger
from app.core.database import SessionLocal
from app.models.database_models import (
    DemandHistory, InventorySnapshot, Batch, Forecast, Recommendation, Transfer, SKU, DistributionCenter
)
from app.services.forecasting_service import ForecastingService
from app.services.recommendation_service import RecommendationService

# Define a stable evaluation date for the demo
DEMO_DATE = date(2026, 8, 12)

def init_system(db):
    """Generates initial forecasts and recommendations for the base demo date."""
    logger.info(f"Initializing baseline forecasting and replenishment plans for {DEMO_DATE}...")
    
    # 1. Run forecasting service to populate forecasts table
    fs = ForecastingService()
    fs.generate_and_save_forecasts(db, DEMO_DATE)
    
    # 2. Run recommendation service to populate recommendations & transfers tables
    rs = RecommendationService()
    rs.generate_recommendations(db, DEMO_DATE)
    logger.info("System initialization complete.")

def trigger_scenario_1(db):
    """
    Scenario 1: Regional Demand Spike
    Spikes demand for MED003 at Bangalore DC (DC002).
    Breaches safety stock and escalates stock-out risk.
    """
    logger.info("Triggering Scenario 1: Bangalore DC demand spike for MED003...")
    
    sku_id = "MED003"
    dc_id = "DC002"
    
    # Modify last 7 days of historical demand to be 3x higher
    start_date = DEMO_DATE - timedelta(days=7)
    records = db.query(DemandHistory).filter(
        DemandHistory.sku_id == sku_id,
        DemandHistory.dc_id == dc_id,
        DemandHistory.date >= start_date,
        DemandHistory.date <= DEMO_DATE
    ).all()
    
    for r in records:
        r.quantity = round(r.quantity * 2.8, 2)
        
    # Reduce available stock to create immediate stockout risk
    inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == sku_id,
        InventorySnapshot.dc_id == dc_id,
        InventorySnapshot.date == DEMO_DATE
    ).first()
    if inv:
        inv.closing_inventory = 110.0
        inv.available_inventory = 100.0
        inv.incoming_inventory = 0.0

    db.commit()
    
    # Regenerate forecasts and recommendations
    init_system(db)
    logger.info("Scenario 1 triggered and database updated successfully!")

def trigger_scenario_2(db):
    """
    Scenario 2: Near-Expiry Transfer (Rebalancing)
    Chennai DC (DC001) has excess stock of MED001 expiring soon (in 25 days),
    while Bangalore DC (DC002) has a severe shortage.
    """
    logger.info("Triggering Scenario 2: Expiry Risk & Transfer between Chennai and Bangalore...")
    
    sku_id = "MED001"
    
    # 1. Chennai (DC001) has excess stock expiring in 25 days
    chennai_dc = "DC001"
    chennai_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == sku_id,
        InventorySnapshot.dc_id == chennai_dc,
        InventorySnapshot.date == DEMO_DATE
    ).first()
    if chennai_inv:
        chennai_inv.closing_inventory = 1200.0
        chennai_inv.available_inventory = 1100.0
        chennai_inv.incoming_inventory = 0.0
        
    # Adjust manufacturing/expiry dates of Chennai batches to expire in 25 days
    exp_date = DEMO_DATE + timedelta(days=25)
    batches = db.query(Batch).filter(
        Batch.sku_id == sku_id,
        Batch.dc_id == chennai_dc
    ).all()
    for idx, b in enumerate(batches):
        b.expiry_date = exp_date
        b.remaining_quantity = 600.0 if idx == 0 else 500.0
        
    # 2. Bangalore (DC002) has shortage
    bangalore_dc = "DC002"
    bangalore_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == sku_id,
        InventorySnapshot.dc_id == bangalore_dc,
        InventorySnapshot.date == DEMO_DATE
    ).first()
    if bangalore_inv:
        bangalore_inv.closing_inventory = 120.0
        bangalore_inv.available_inventory = 100.0
        bangalore_inv.incoming_inventory = 0.0

    db.commit()
    
    # Regenerate forecasts and recommendations
    init_system(db)
    logger.info("Scenario 2 triggered and database updated successfully!")

def trigger_scenario_3(db):
    """
    Scenario 3: Cross-DC Shortage Resolution
    Bangalore shortage -> system checks other DCs -> finds Chennai excess -> recommends transfer ->
    Chennai doesn't have enough excess -> system triggers a secondary supplier replenishment order for remainder.
    """
    logger.info("Triggering Scenario 3: Joint Transfer + Replenishment logic...")
    
    sku_id = "MED005"
    
    # Bangalore (DC002) has HUGE shortage (needs 1200 units, but standard inventory is very low)
    bangalore_dc = "DC002"
    bangalore_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == sku_id,
        InventorySnapshot.dc_id == bangalore_dc,
        InventorySnapshot.date == DEMO_DATE
    ).first()
    if bangalore_inv:
        bangalore_inv.closing_inventory = 50.0
        bangalore_inv.available_inventory = 40.0
        bangalore_inv.incoming_inventory = 0.0
        
    # Chennai (DC001) has excess stock, but only 400 units
    chennai_dc = "DC001"
    chennai_inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == sku_id,
        InventorySnapshot.dc_id == chennai_dc,
        InventorySnapshot.date == DEMO_DATE
    ).first()
    if chennai_inv:
        chennai_inv.closing_inventory = 700.0
        chennai_inv.available_inventory = 650.0
        
    # Adjust Chennai batches
    batches = db.query(Batch).filter(
        Batch.sku_id == sku_id,
        Batch.dc_id == chennai_dc
    ).all()
    for idx, b in enumerate(batches):
        b.expiry_date = DEMO_DATE + timedelta(days=35) # Expiring soon
        b.remaining_quantity = 400.0 if idx == 0 else 0.0

    db.commit()
    
    # Regenerate forecasts and recommendations
    init_system(db)
    logger.info("Scenario 3 triggered and database updated successfully!")

def trigger_scenario_4(db):
    """
    Scenario 4: Stable Inventory
    Resets MED008 across all DCs to healthy stock, ensuring NO recommendations are generated.
    """
    logger.info("Triggering Scenario 4: Reseting MED008 to Stable/Healthy state...")
    
    sku_id = "MED008"
    for dc in db.query(DistributionCenter).all():
        inv = db.query(InventorySnapshot).filter(
            InventorySnapshot.sku_id == sku_id,
            InventorySnapshot.dc_id == dc.dc_id,
            InventorySnapshot.date == DEMO_DATE
        ).first()
        if inv:
            inv.closing_inventory = 800.0
            inv.available_inventory = 750.0
            inv.incoming_inventory = 0.0
            
        # Ensure batches expire far in the future
        batches = db.query(Batch).filter(
            Batch.sku_id == sku_id,
            Batch.dc_id == dc.dc_id
        ).all()
        for b in batches:
            b.expiry_date = DEMO_DATE + timedelta(days=400)
            
    db.commit()
    init_system(db)
    logger.info("Scenario 4 triggered and database updated successfully!")

def trigger_scenario_5(db):
    """
    Scenario 5: Critical Medicine Shortage
    Emergency category medicine MED015 hits a low stock level.
    Triggers CRITICAL escalation priority immediately.
    """
    logger.info("Triggering Scenario 5: Critical emergency medicine MED015 shortage escalation...")
    
    sku_id = "MED015"
    
    # Ensure SKU is Criticality = CRITICAL
    sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
    if sku:
        sku.criticality = "CRITICAL"
        sku.category = "Emergency"
        
    # Drain stock at Delhi DC (DC005)
    dc_id = "DC005"
    inv = db.query(InventorySnapshot).filter(
        InventorySnapshot.sku_id == sku_id,
        InventorySnapshot.dc_id == dc_id,
        InventorySnapshot.date == DEMO_DATE
    ).first()
    if inv:
        inv.closing_inventory = 30.0
        inv.available_inventory = 25.0
        inv.incoming_inventory = 0.0
        
    db.commit()
    init_system(db)
    logger.info("Scenario 5 triggered and database updated successfully!")

def main():
    parser = argparse.ArgumentParser(description="MedCare AI Demo Scenario Runner")
    parser.add_argument("--init", action="store_true", help="Initialize baseline forecasts & recommendations")
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3, 4, 5], help="Scenario number to execute")
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if args.init:
            init_system(db)
        elif args.scenario == 1:
            trigger_scenario_1(db)
        elif args.scenario == 2:
            trigger_scenario_2(db)
        elif args.scenario == 3:
            trigger_scenario_3(db)
        elif args.scenario == 4:
            trigger_scenario_4(db)
        elif args.scenario == 5:
            trigger_scenario_5(db)
        else:
            # If no args, run init
            init_system(db)
    except Exception as e:
        logger.error(f"Error executing demo commands: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
