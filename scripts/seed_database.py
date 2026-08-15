import sys
import os
import pandas as pd
from datetime import datetime

# Adjust path to enable importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging_config import logger
from app.core.database import SessionLocal, engine
from app.models.database_models import (
    Base, SKU, DistributionCenter, Supplier, SKU_Supplier,
    Promotion, DemandHistory, DistributorOrder, InventorySnapshot, Batch
)

def parse_date(date_str):
    if pd.isna(date_str):
        return None
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.strptime(str(date_str), "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            return None

def seed_db():
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if database is already seeded by counting SKUs
        if db.query(SKU).count() > 0:
            logger.info("Database is already seeded. Clearing old entries for re-seeding...")
            db.query(DemandHistory).delete()
            db.query(InventorySnapshot).delete()
            db.query(DistributorOrder).delete()
            db.query(Batch).delete()
            db.query(Promotion).delete()
            db.query(SKU_Supplier).delete()
            db.query(Supplier).delete()
            db.query(DistributionCenter).delete()
            db.query(SKU).delete()
            db.commit()

        logger.info("Seeding SKUs...")
        df_skus = pd.read_csv("data/processed/skus.csv")
        for _, r in df_skus.iterrows():
            db.add(SKU(
                sku_id=r["sku_id"],
                name=r["name"],
                category=r["category"],
                therapeutic_class=r["therapeutic_class"],
                unit_cost=r["unit_cost"],
                criticality=r["criticality"],
                shelf_life_days=r["shelf_life_days"],
                base_demand=r["base_demand"],
                demand_variability=r["demand_variability"],
                min_order_qty=r["min_order_qty"]
            ))
            
        logger.info("Seeding Distribution Centers...")
        df_dcs = pd.read_csv("data/processed/dcs.csv")
        for _, r in df_dcs.iterrows():
            db.add(DistributionCenter(
                dc_id=r["dc_id"],
                name=r["name"],
                location=r["location"],
                region=r["region"],
                storage_capacity=r["storage_capacity"],
                lead_time_days=r["lead_time_days"],
                service_priority=r["service_priority"]
            ))

        logger.info("Seeding Suppliers...")
        df_sups = pd.read_csv("data/processed/suppliers.csv")
        for _, r in df_sups.iterrows():
            db.add(Supplier(
                supplier_id=r["supplier_id"],
                name=r["name"],
                reliability_score=r["reliability_score"]
            ))
        db.commit() # Commit parents to allow FK lookups

        logger.info("Seeding SKU-Supplier mappings...")
        df_sku_sups = pd.read_csv("data/processed/sku_suppliers.csv")
        for _, r in df_sku_sups.iterrows():
            db.add(SKU_Supplier(
                sku_id=r["sku_id"],
                supplier_id=r["supplier_id"],
                dc_id=r["dc_id"],
                lead_time_days=r["lead_time_days"]
            ))

        logger.info("Seeding Promotions...")
        df_promotions = pd.read_csv("data/processed/promotions.csv")
        for _, r in df_promotions.iterrows():
            db.add(Promotion(
                promotion_id=r["promotion_id"],
                sku_id=r["sku_id"],
                dc_id=r["dc_id"],
                promotion_type=r["promotion_type"],
                discount_percentage=r["discount_percentage"],
                start_date=parse_date(r["start_date"]),
                end_date=parse_date(r["end_date"])
            ))

        logger.info("Seeding Batches...")
        df_batches = pd.read_csv("data/processed/batches.csv")
        for _, r in df_batches.iterrows():
            db.add(Batch(
                batch_id=r["batch_id"],
                sku_id=r["sku_id"],
                dc_id=r["dc_id"],
                manufacturing_date=parse_date(r["manufacturing_date"]),
                expiry_date=parse_date(r["expiry_date"]),
                initial_quantity=r["initial_quantity"],
                remaining_quantity=r["remaining_quantity"]
            ))

        logger.info("Seeding Distributor Orders...")
        df_orders = pd.read_csv("data/processed/distributor_orders.csv")
        # To avoid SQLite bottleneck on large insert sizes, use bulk insert mapping or commit in chunks
        orders_to_add = []
        for _, r in df_orders.iterrows():
            orders_to_add.append(DistributorOrder(
                order_id=r["order_id"],
                order_date=parse_date(r["order_date"]),
                sku_id=r["sku_id"],
                dc_id=r["dc_id"],
                ordered_quantity=r["ordered_quantity"],
                fulfilled_quantity=r["fulfilled_quantity"],
                status=r["status"]
            ))
        db.bulk_save_objects(orders_to_add)

        logger.info("Seeding Demand History...")
        df_demand = pd.read_csv("data/processed/demand_history.csv")
        demand_to_add = []
        for _, r in df_demand.iterrows():
            demand_to_add.append(DemandHistory(
                date=parse_date(r["date"]),
                sku_id=r["sku_id"],
                dc_id=r["dc_id"],
                quantity=r["quantity"],
                is_promotional=bool(r["is_promotional"]),
                out_of_stock_lost_sales=r["out_of_stock_lost_sales"]
            ))
        db.bulk_save_objects(demand_to_add)

        logger.info("Seeding Inventory Snapshots...")
        df_inv = pd.read_csv("data/processed/inventory_snapshots.csv")
        inv_to_add = []
        for _, r in df_inv.iterrows():
            inv_to_add.append(InventorySnapshot(
                date=parse_date(r["date"]),
                sku_id=r["sku_id"],
                dc_id=r["dc_id"],
                opening_inventory=r["opening_inventory"],
                incoming_inventory=r["incoming_inventory"],
                outgoing_inventory=r["outgoing_inventory"],
                closing_inventory=r["closing_inventory"],
                reserved_inventory=r["reserved_inventory"],
                available_inventory=r["available_inventory"]
            ))
        db.bulk_save_objects(inv_to_add)

        db.commit()
        logger.info("Database seeded successfully!")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
