import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from app.core.logging_config import logger

def generate_synthetic_dataset(seed: int = 42, num_days: int = 180):
    """
    Generates a realistic pharmaceutical supply chain dataset.
    Generates around 30,000 - 60,000 transactional rows.
    """
    logger.info(f"Starting synthetic data generation with seed={seed}, num_days={num_days}")
    random.seed(seed)
    np.random.seed(seed)

    # 1. Generate SKUs Master Data (40 SKUs)
    categories = [
        ("Antibiotic", "Infectious Diseases", "HIGH"),
        ("Analgesic", "Pain Management", "LOW"),
        ("Antipyretic", "Fever control", "LOW"),
        ("Cardiovascular", "Heart Care", "CRITICAL"),
        ("Diabetes", "Endocrinology", "CRITICAL"),
        ("Respiratory", "Pulmonology", "HIGH"),
        ("Gastrointestinal", "Stomach Care", "MEDIUM"),
        ("Vitamin", "Nutrition", "LOW"),
        ("Emergency", "Critical Care", "CRITICAL")
    ]
    
    skus_list = []
    for i in range(1, 41):
        sku_id = f"MED{i:03d}"
        cat_info = random.choice(categories)
        category, therapeutic, criticality = cat_info
        
        # Base demand and variability depending on category
        if criticality == "CRITICAL":
            base_dem = random.uniform(50, 150)
            variability = random.uniform(0.1, 0.25)
        elif category == "Respiratory": # High seasonal variability
            base_dem = random.uniform(30, 100)
            variability = random.uniform(0.4, 0.7)
        else:
            base_dem = random.uniform(20, 80)
            variability = random.uniform(0.2, 0.4)
            
        unit_cost = round(random.uniform(5.0, 120.0), 2)
        shelf_life = random.randint(180, 540) # Days
        min_order = random.choice([50, 100, 200, 500])
        
        skus_list.append({
            "sku_id": sku_id,
            "name": f"Medication-{category[:3].upper()}-{i}",
            "category": category,
            "therapeutic_class": therapeutic,
            "unit_cost": unit_cost,
            "criticality": criticality,
            "shelf_life_days": shelf_life,
            "base_demand": round(base_dem, 2),
            "demand_variability": round(variability, 2),
            "min_order_qty": min_order
        })
    df_skus = pd.DataFrame(skus_list)

    # 2. Generate Distribution Centers Master Data (8 DCs)
    dcs_list = [
        {"dc_id": "DC001", "name": "Chennai DC", "location": "Chennai", "region": "South", "storage_capacity": 50000, "lead_time_days": 5, "service_priority": 1},
        {"dc_id": "DC002", "name": "Bangalore DC", "location": "Bangalore", "region": "South", "storage_capacity": 45000, "lead_time_days": 4, "service_priority": 2},
        {"dc_id": "DC003", "name": "Hyderabad DC", "location": "Hyderabad", "region": "South", "storage_capacity": 40000, "lead_time_days": 4, "service_priority": 2},
        {"dc_id": "DC004", "name": "Mumbai DC", "location": "Mumbai", "region": "West", "storage_capacity": 60000, "lead_time_days": 6, "service_priority": 1},
        {"dc_id": "DC005", "name": "Delhi DC", "location": "Delhi", "region": "North", "storage_capacity": 55000, "lead_time_days": 7, "service_priority": 1},
        {"dc_id": "DC006", "name": "Kolkata DC", "location": "Kolkata", "region": "East", "storage_capacity": 35000, "lead_time_days": 8, "service_priority": 3},
        {"dc_id": "DC007", "name": "Pune DC", "location": "Pune", "region": "West", "storage_capacity": 30000, "lead_time_days": 5, "service_priority": 3},
        {"dc_id": "DC008", "name": "Ahmedabad DC", "location": "Ahmedabad", "region": "West", "storage_capacity": 35000, "lead_time_days": 6, "service_priority": 3}
    ]
    df_dcs = pd.DataFrame(dcs_list)

    # 3. Suppliers (5 Suppliers)
    suppliers_list = [
        {"supplier_id": "SUP001", "name": "PharmaCorp Industries", "reliability_score": 0.96},
        {"supplier_id": "SUP002", "name": "Apex BioLabs", "reliability_score": 0.94},
        {"supplier_id": "SUP003", "name": "Global Pharma Ltd", "reliability_score": 0.89},
        {"supplier_id": "SUP004", "name": "MediSolutions Inc", "reliability_score": 0.97},
        {"supplier_id": "SUP005", "name": "Zenith Therapeutics", "reliability_score": 0.92}
    ]
    df_suppliers = pd.DataFrame(suppliers_list)

    # SKU-Supplier mappings with localized lead times
    sku_suppliers_list = []
    for sku in skus_list:
        # Each SKU has 1-2 suppliers
        num_sups = random.choice([1, 2])
        assigned_sups = random.sample(suppliers_list, num_sups)
        for sup in assigned_sups:
            for dc in dcs_list:
                # lead time based on DC's baseline + supplier variance
                base_lt = dc["lead_time_days"]
                lt = max(2, base_lt + random.randint(-2, 2))
                sku_suppliers_list.append({
                    "sku_id": sku["sku_id"],
                    "supplier_id": sup["supplier_id"],
                    "dc_id": dc["dc_id"],
                    "lead_time_days": lt
                })
    df_sku_suppliers = pd.DataFrame(sku_suppliers_list)

    # 4. Generate Promotions
    # 2 promotions active at any given time per region/SKU category
    promotions_list = []
    start_anchor = datetime.now() - timedelta(days=num_days)
    for p_idx in range(1, 21):
        promo_sku = random.choice(skus_list)["sku_id"]
        promo_dc = random.choice(dcs_list)["dc_id"]
        p_start_offset = random.randint(10, num_days - 20)
        p_duration = random.randint(5, 15)
        p_start = (start_anchor + timedelta(days=p_start_offset)).date()
        p_end = p_start + timedelta(days=p_duration)
        discount = random.choice([0.1, 0.15, 0.2, 0.25])
        promotions_list.append({
            "promotion_id": f"PRM{p_idx:03d}",
            "sku_id": promo_sku,
            "dc_id": promo_dc,
            "promotion_type": random.choice(["Discount", "BOGO", "Seasonal Bundle"]),
            "discount_percentage": discount,
            "start_date": p_start,
            "end_date": p_end
        })
    df_promotions = pd.DataFrame(promotions_list)

    # 5. Generate Demand History and Inventory Snapshots (Daily loop)
    # Target date range
    dates = [start_anchor.date() + timedelta(days=d) for d in range(num_days)]
    
    demand_history_list = []
    inventory_snapshots_list = []
    distributor_orders_list = []
    batches_list = []

    # Pre-generate some starting batches for all DC/SKUs to represent initial stock
    batch_counter = 1
    initial_stock_map = {} # (sku, dc) -> current inventory
    
    # Store dynamic state for inventory tracking
    current_inventory_levels = {} # (sku, dc) -> closing inventory

    for sku in skus_list:
        for dc in dcs_list:
            # We create 2-3 starting batches
            num_batches = random.randint(2, 4)
            total_qty = 0
            for b in range(num_batches):
                b_qty = round(random.uniform(200, 1000), 0)
                total_qty += b_qty
                # Manufacturing date in the past
                mfg_offset = random.randint(30, 150)
                mfg_date = (start_anchor - timedelta(days=mfg_offset)).date()
                # Expiry date
                exp_date = mfg_date + timedelta(days=sku["shelf_life_days"])
                batch_id = f"BAT{batch_counter:05d}"
                batches_list.append({
                    "batch_id": batch_id,
                    "sku_id": sku["sku_id"],
                    "dc_id": dc["dc_id"],
                    "manufacturing_date": mfg_date,
                    "expiry_date": exp_date,
                    "initial_quantity": b_qty,
                    "remaining_quantity": b_qty
                })
                batch_counter += 1
            
            initial_stock_map[(sku["sku_id"], dc["dc_id"])] = total_qty
            current_inventory_levels[(sku["sku_id"], dc["dc_id"])] = total_qty

    # Track scheduled incoming deliveries: list of dicts {date, sku_id, dc_id, qty}
    incoming_shipments = []

    logger.info("Simulating daily demand and inventory dynamics...")
    for day_idx, d_date in enumerate(dates):
        day_of_week = d_date.weekday() # 0 = Monday, 6 = Sunday
        month = d_date.month
        
        # Check active promotions
        active_promos_map = {} # (sku, dc) -> discount_pct
        for promo in promotions_list:
            if promo["start_date"] <= d_date <= promo["end_date"]:
                active_promos_map[(promo["sku_id"], promo["dc_id"])] = promo["discount_percentage"]

        # Loop combinations
        for sku in skus_list:
            sku_id = sku["sku_id"]
            for dc in dcs_list:
                dc_id = dc["dc_id"]
                key = (sku_id, dc_id)
                
                # Check for arriving shipments
                arrived_qty = 0
                incoming_shipments = [ship for ship in incoming_shipments if not (ship["date"] == d_date and ship["sku_id"] == sku_id and ship["dc_id"] == dc_id and (arrived_qty := ship["qty"]))]
                
                # Calculate incoming pipeline (in-transit but not yet arrived)
                pipeline_qty = sum(ship["qty"] for ship in incoming_shipments if ship["sku_id"] == sku_id and ship["dc_id"] == dc_id and ship["date"] > d_date)
                
                # Opening inventory is yesterday's closing
                opening_stock = current_inventory_levels[key]
                
                # Calculate incoming inventory
                incoming_stock = arrived_qty
                
                # Process FEFO logic for batches to expire items
                # Filter active batches for this SKU/DC
                active_batches = [b for b in batches_list if b["sku_id"] == sku_id and b["dc_id"] == dc_id and b["remaining_quantity"] > 0]
                # If batches expire today, they are deducted from inventory as wastage
                expired_qty = 0
                for b in active_batches:
                    if b["expiry_date"] <= d_date:
                        expired_qty += b["remaining_quantity"]
                        b["remaining_quantity"] = 0.0
                
                opening_stock = max(0.0, opening_stock - expired_qty)
                
                # 1. Base Demand
                base = sku["base_demand"]
                
                # 2. Seasonality factor
                # Respiratory medicines spike in Winter (Dec, Jan, Feb)
                if sku["category"] == "Respiratory":
                    if month in [12, 1, 2]:
                        seasonality = 1.6
                    elif month in [6, 7, 8]:
                        seasonality = 0.6
                    else:
                        seasonality = 1.0
                # Allergy/Antipyretic spike in Monsoon/Spring
                elif sku["category"] in ["Analgesic", "Antipyretic"]:
                    if month in [6, 7, 8, 9]: # Monsoon outbreaks
                        seasonality = 1.3
                    else:
                        seasonality = 0.95
                else:
                    # Minor baseline seasonality
                    seasonality = 1.0 + 0.15 * np.sin(2 * np.pi * d_date.timetuple().tm_yday / 365.0)

                # 3. Regional factor
                # Different DCs have regional modifiers
                if dc["region"] == "North" and sku["category"] == "Respiratory":
                    regional_factor = 1.25 # Delhi respiratory issues
                elif dc["region"] == "South" and sku["category"] == "Cardiovascular":
                    regional_factor = 1.15
                else:
                    regional_factor = 1.0

                # 4. Promotion factor
                discount = active_promos_map.get(key, 0.0)
                promo_active = discount > 0.0
                promo_factor = 1.0 + (discount * 1.5) if promo_active else 1.0
                
                # 5. Weekly pattern (lower demand on weekends)
                weekday_factor = 0.7 if day_of_week in [5, 6] else 1.1
                
                # 6. Trend
                trend = 0.02 * day_idx # Gradual growth
                
                # 7. Noise
                noise = np.random.normal(0, base * sku["demand_variability"])
                
                # Final demand calculation
                raw_demand = (base * seasonality * regional_factor * promo_factor * weekday_factor) + trend + noise
                demand_qty = max(0.0, round(raw_demand, 2))
                
                # Out of stock calculation & physical outgoing shipment
                # Available stock is opening + incoming
                available_to_serve = opening_stock + incoming_stock
                
                if available_to_serve >= demand_qty:
                    outgoing_qty = demand_qty
                    lost_sales = 0.0
                else:
                    outgoing_qty = available_to_serve
                    lost_sales = demand_qty - available_to_serve
                    
                # Deduct from batches using FEFO
                # Re-fetch active batches
                active_batches = [b for b in batches_list if b["sku_id"] == sku_id and b["dc_id"] == dc_id and b["remaining_quantity"] > 0]
                active_batches.sort(key=lambda x: x["expiry_date"])
                
                qty_to_deduct = outgoing_qty
                for b in active_batches:
                    if qty_to_deduct <= 0:
                        break
                    deduct = min(b["remaining_quantity"], qty_to_deduct)
                    b["remaining_quantity"] -= deduct
                    qty_to_deduct -= deduct
                    
                # Closing inventory
                closing_stock = max(0.0, opening_stock + incoming_stock - outgoing_qty)
                current_inventory_levels[key] = closing_stock
                
                # Reserved inventory is some random fraction (e.g. 5-15% of closing stock) representing orders in system
                reserved_stock = round(closing_stock * random.uniform(0.05, 0.15), 0)
                available_for_orders = max(0.0, closing_stock - reserved_stock)
                
                # Append demand record
                demand_history_list.append({
                    "date": d_date,
                    "sku_id": sku_id,
                    "dc_id": dc_id,
                    "quantity": demand_qty,
                    "is_promotional": promo_active,
                    "out_of_stock_lost_sales": lost_sales
                })
                
                # Append inventory snapshot
                inventory_snapshots_list.append({
                    "date": d_date,
                    "sku_id": sku_id,
                    "dc_id": dc_id,
                    "opening_inventory": opening_stock,
                    "incoming_inventory": pipeline_qty,  # Goods currently in transit
                    "outgoing_inventory": outgoing_qty,
                    "closing_inventory": closing_stock,
                    "reserved_inventory": reserved_stock,
                    "available_inventory": available_for_orders
                })

                # Distributor orders: generate daily order requests representing B2B signals
                # These are usually correlated with demand
                if random.random() < 0.7:
                    ordered_qty = round(demand_qty * random.uniform(0.9, 1.3) + random.uniform(0, 10), 0)
                    fulfilled_qty = min(ordered_qty, available_for_orders)
                    order_status = "FULFILLED" if fulfilled_qty == ordered_qty else ("PARTIAL" if fulfilled_qty > 0 else "PENDING")
                    distributor_orders_list.append({
                        "order_id": f"ORD{len(distributor_orders_list) + 1:06d}",
                        "order_date": d_date,
                        "sku_id": sku_id,
                        "dc_id": dc_id,
                        "ordered_quantity": ordered_qty,
                        "fulfilled_quantity": fulfilled_qty,
                        "status": order_status
                    })
                
                # Simple logic for automatic reorders during simulation to keep inventory healthy:
                # If closing stock goes below a threshold, schedule an incoming order
                # The threshold represents a simple reorder point
                add = max(5.0, base)
                lead_time = dc["lead_time_days"]
                rop = add * lead_time * 1.5
                if closing_stock < rop and pipeline_qty == 0:
                    order_qty = round(add * 10, 0)
                    arrival_date = d_date + timedelta(days=lead_time)
                    incoming_shipments.append({
                        "date": arrival_date,
                        "sku_id": sku_id,
                        "dc_id": dc_id,
                        "qty": order_qty
                    })
                    
                    # Create a new batch for this arriving shipment
                    batch_id = f"BAT{batch_counter:05d}"
                    batches_list.append({
                        "batch_id": batch_id,
                        "sku_id": sku_id,
                        "dc_id": dc_id,
                        "manufacturing_date": arrival_date,
                        "expiry_date": arrival_date + timedelta(days=sku["shelf_life_days"]),
                        "initial_quantity": order_qty,
                        "remaining_quantity": order_qty
                    })
                    batch_counter += 1

    df_demand = pd.DataFrame(demand_history_list)
    df_inventory = pd.DataFrame(inventory_snapshots_list)
    df_orders = pd.DataFrame(distributor_orders_list)
    df_batches = pd.DataFrame(batches_list)

    # 6. Inject Data Quality Imperfections (~0.5% anomalies)
    logger.info("Injecting realistic data-quality issues...")
    
    # Missing values in demand quantity
    missing_indices = df_demand.sample(frac=0.005, random_state=42).index
    df_demand.loc[missing_indices, "quantity"] = np.nan
    
    # Outliers in demand (e.g. multiplied by 10)
    outlier_indices = df_demand.sample(frac=0.005, random_state=100).index
    df_demand.loc[outlier_indices, "quantity"] = df_demand.loc[outlier_indices, "quantity"] * 12.0

    # Duplicated transactions
    dupes = df_demand.sample(frac=0.005, random_state=200)
    df_demand = pd.concat([df_demand, dupes], ignore_index=True)
    
    # Ensure directory existence
    os.makedirs("data/synthetic", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)

    # Save synthetic raw datasets
    df_skus.to_csv("data/synthetic/skus.csv", index=False)
    df_dcs.to_csv("data/synthetic/dcs.csv", index=False)
    df_suppliers.to_csv("data/synthetic/suppliers.csv", index=False)
    df_sku_suppliers.to_csv("data/synthetic/sku_suppliers.csv", index=False)
    df_promotions.to_csv("data/synthetic/promotions.csv", index=False)
    df_demand.to_csv("data/synthetic/demand_history.csv", index=False)
    df_orders.to_csv("data/synthetic/distributor_orders.csv", index=False)
    df_inventory.to_csv("data/synthetic/inventory_snapshots.csv", index=False)
    df_batches.to_csv("data/synthetic/batches.csv", index=False)
    
    # Save copies to data/raw/
    df_skus.to_csv("data/raw/skus.csv", index=False)
    df_dcs.to_csv("data/raw/dcs.csv", index=False)
    df_suppliers.to_csv("data/raw/suppliers.csv", index=False)
    df_sku_suppliers.to_csv("data/raw/sku_suppliers.csv", index=False)
    df_promotions.to_csv("data/raw/promotions.csv", index=False)
    df_demand.to_csv("data/raw/demand_history.csv", index=False)
    df_orders.to_csv("data/raw/distributor_orders.csv", index=False)
    df_inventory.to_csv("data/raw/inventory_snapshots.csv", index=False)
    df_batches.to_csv("data/raw/batches.csv", index=False)

    logger.info("Synthetic dataset generated and saved successfully!")
    return df_skus, df_dcs, df_suppliers, df_sku_suppliers, df_promotions, df_demand, df_orders, df_inventory, df_batches

if __name__ == "__main__":
    generate_synthetic_dataset()
