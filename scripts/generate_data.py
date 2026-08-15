import sys
import os

# Adjust path to enable importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.generator import generate_synthetic_dataset
from app.core.logging_config import logger

def main():
    logger.info("Initializing synthetic data generation...")
    skus, dcs, sups, sku_sups, promos, demand, orders, inv, batches = generate_synthetic_dataset(seed=42)
    
    print("\n" + "="*50)
    print("SYNTHETIC DATA SUMMARY:")
    print("="*50)
    print(f"SKUs: {len(skus)} rows")
    print(f"Distribution Centers: {len(dcs)} rows")
    print(f"Suppliers: {len(sups)} rows")
    print(f"SKU-Supplier mappings: {len(sku_sups)} rows")
    print(f"Promotions: {len(promos)} rows")
    print(f"Demand History (Raw): {len(demand)} rows")
    print(f"Distributor Orders: {len(orders)} rows")
    print(f"Inventory Snapshots: {len(inv)} rows")
    print(f"Batches: {len(batches)} rows")
    print("="*50 + "\n")
    logger.info("Data generation script finished successfully.")

if __name__ == "__main__":
    main()
