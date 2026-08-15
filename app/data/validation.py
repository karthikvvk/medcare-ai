import pandas as pd
from app.core.logging_config import logger

def validate_datasets():
    """
    Validates the schemas and profiles the raw datasets.
    Returns True if valid, False if critical checks fail.
    """
    logger.info("Starting raw dataset validation...")
    
    required_files = {
        "skus": "data/raw/skus.csv",
        "dcs": "data/raw/dcs.csv",
        "suppliers": "data/raw/suppliers.csv",
        "sku_suppliers": "data/raw/sku_suppliers.csv",
        "promotions": "data/raw/promotions.csv",
        "demand_history": "data/raw/demand_history.csv",
        "distributor_orders": "data/raw/distributor_orders.csv",
        "inventory_snapshots": "data/raw/inventory_snapshots.csv",
        "batches": "data/raw/batches.csv"
    }
    
    # Check if all files exist
    for name, path in required_files.items():
        if not os.path.exists(path):
            logger.error(f"Validation failed: missing required file '{path}'")
            return False
            
    # Load and check column structures
    try:
        df_demand = pd.read_csv(required_files["demand_history"])
        df_inv = pd.read_csv(required_files["inventory_snapshots"])
        df_skus = pd.read_csv(required_files["skus"])
        
        # Check demand cols
        demand_cols = {"date", "sku_id", "dc_id", "quantity", "is_promotional", "out_of_stock_lost_sales"}
        if not demand_cols.issubset(df_demand.columns):
            logger.error(f"Validation failed: demand_history schema mismatch. Expected keys: {demand_cols}")
            return False
            
        # Check inventory cols
        inv_cols = {"date", "sku_id", "dc_id", "opening_inventory", "closing_inventory", "available_inventory"}
        if not inv_cols.issubset(df_inv.columns):
            logger.error(f"Validation failed: inventory_snapshots schema mismatch. Expected keys: {inv_cols}")
            return False

        # Check for duplicate row rates
        demand_duplicates = df_demand.duplicated().sum()
        logger.info(f"Validation: found {demand_duplicates} duplicates in raw demand history.")
        
        # Check for null rate
        demand_nulls = df_demand["quantity"].isnull().sum()
        logger.info(f"Validation: found {demand_nulls} missing values in raw demand history.")
        
        # Check SKU references
        unique_demand_skus = set(df_demand["sku_id"].unique())
        master_skus = set(df_skus["sku_id"].unique())
        unmatched_skus = unique_demand_skus - master_skus
        if unmatched_skus:
            logger.warning(f"Validation warning: demand contains SKUs not in master: {unmatched_skus}")

        logger.info("Raw datasets validated successfully!")
        return True
    except Exception as e:
        logger.error(f"Exception during dataset validation: {e}")
        return False

import os
if __name__ == "__main__":
    validate_datasets()
