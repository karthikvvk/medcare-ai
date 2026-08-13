import os
import pandas as pd
import numpy as np
from app.core.logging_config import logger

def clean_raw_data():
    """
    Cleans raw data from data/raw/ and saves processed datasets to data/processed/.
    - Drops duplicates.
    - Handles missing values by filling with group median.
    - Removes outliers by clipping values using IQR.
    """
    logger.info("Cleaning raw datasets...")
    
    os.makedirs("data/processed", exist_ok=True)
    
    # 1. Load data
    df_demand = pd.read_csv("data/raw/demand_history.csv")
    df_inv = pd.read_csv("data/raw/inventory_snapshots.csv")
    df_skus = pd.read_csv("data/raw/skus.csv")
    df_dcs = pd.read_csv("data/raw/dcs.csv")
    df_suppliers = pd.read_csv("data/raw/suppliers.csv")
    df_sku_suppliers = pd.read_csv("data/raw/sku_suppliers.csv")
    df_promotions = pd.read_csv("data/raw/promotions.csv")
    df_orders = pd.read_csv("data/raw/distributor_orders.csv")
    df_batches = pd.read_csv("data/raw/batches.csv")

    # 2. Process demand duplicates
    initial_len = len(df_demand)
    df_demand = df_demand.drop_duplicates()
    logger.info(f"Deduplicated demand: removed {initial_len - len(df_demand)} duplicates.")

    # 3. Handle missing values in demand
    # Fill missing quantity with the median for that SKU/DC combo, fallback to SKU median, fallback to 0.0
    group_medians = df_demand.groupby(["sku_id", "dc_id"])["quantity"].transform("median")
    sku_medians = df_demand.groupby("sku_id")["quantity"].transform("median")
    
    df_demand["quantity"] = df_demand["quantity"].fillna(group_medians)
    df_demand["quantity"] = df_demand["quantity"].fillna(sku_medians)
    df_demand["quantity"] = df_demand["quantity"].fillna(0.0)

    # 4. Handle outliers using rolling or IQR method per SKU/DC
    # We clip values above Q3 + 3*IQR
    def clip_outliers(group):
        q1 = group["quantity"].quantile(0.25)
        q3 = group["quantity"].quantile(0.75)
        iqr = q3 - q1
        upper_limit = q3 + 3.0 * iqr
        if iqr > 0:
            group["quantity"] = group["quantity"].clip(upper=upper_limit)
        return group
        
    df_demand = df_demand.groupby(["sku_id", "dc_id"], group_keys=False).apply(clip_outliers)
    logger.info("Outliers cleaned using IQR clipping method.")

    # 5. Save all datasets to data/processed/
    df_demand.to_csv("data/processed/demand_history.csv", index=False)
    df_inv.to_csv("data/processed/inventory_snapshots.csv", index=False)
    df_skus.to_csv("data/processed/skus.csv", index=False)
    df_dcs.to_csv("data/processed/dcs.csv", index=False)
    df_suppliers.to_csv("data/processed/suppliers.csv", index=False)
    df_sku_suppliers.to_csv("data/processed/sku_suppliers.csv", index=False)
    df_promotions.to_csv("data/processed/promotions.csv", index=False)
    df_orders.to_csv("data/processed/distributor_orders.csv", index=False)
    df_batches.to_csv("data/processed/batches.csv", index=False)
    
    logger.info("Processed datasets saved to data/processed/")
    return df_demand

def build_features(df_demand=None, df_inv=None, is_training: bool = True):
    """
    Builds forecasting features from demand and inventory histories.
    Combines them into a single dataframe ready for training or prediction.
    Features are designed to prevent data leakage.
    """
    logger.info("Engineering forecasting features...")
    
    if df_demand is None:
        df_demand = pd.read_csv("data/processed/demand_history.csv")
    if df_inv is None:
        df_inv = pd.read_csv("data/processed/inventory_snapshots.csv")
        
    # Cast dates
    df_demand["date"] = pd.to_datetime(df_demand["date"])
    df_inv["date"] = pd.to_datetime(df_inv["date"])
    
    # Sort
    df_demand = df_demand.sort_values(by=["sku_id", "dc_id", "date"]).reset_index(drop=True)
    df_inv = df_inv.sort_values(by=["sku_id", "dc_id", "date"]).reset_index(drop=True)
    
    # Pre-merge inventory snapshots so we have historical stock level signals
    # Use closing inventory of day t as a feature for forecasting day t+1
    df_merged = pd.merge(
        df_demand, 
        df_inv[["date", "sku_id", "dc_id", "closing_inventory", "available_inventory"]], 
        on=["date", "sku_id", "dc_id"], 
        how="left"
    )
    
    features_list = []
    
    # Group by SKU + DC
    grouped = df_merged.groupby(["sku_id", "dc_id"])
    for name, group in grouped:
        group = group.copy()
        
        # Calendar features
        group["day_of_week"] = group["date"].dt.dayofweek
        group["week_of_year"] = group["date"].dt.isocalendar().week.astype(int)
        group["month"] = group["date"].dt.month
        group["quarter"] = group["date"].dt.quarter
        group["is_weekend"] = group["day_of_week"].isin([5, 6]).astype(int)
        
        # Lag features (strictly past values)
        group["lag_1"] = group["quantity"].shift(1)
        group["lag_3"] = group["quantity"].shift(3)
        group["lag_7"] = group["quantity"].shift(7)
        group["lag_14"] = group["quantity"].shift(14)
        group["lag_21"] = group["quantity"].shift(21)
        group["lag_28"] = group["quantity"].shift(28)
        
        # Rolling features (use shift(1) to avoid data leakage)
        # Shifted rolling mean represent history up to day t-1
        group["rolling_mean_7"] = group["quantity"].shift(1).rolling(7).mean()
        group["rolling_mean_14"] = group["quantity"].shift(1).rolling(14).mean()
        group["rolling_mean_28"] = group["quantity"].shift(1).rolling(28).mean()
        
        group["rolling_std_7"] = group["quantity"].shift(1).rolling(7).std()
        group["rolling_std_14"] = group["quantity"].shift(1).rolling(14).std()
        
        # Demand signals
        # Growth indicator: rolling 7 mean divided by rolling 28 mean
        group["recent_demand_growth"] = group["rolling_mean_7"] / (group["rolling_mean_28"] + 1e-5)
        # Velocity: difference in rolling averages
        group["demand_velocity"] = group["rolling_mean_7"] - group["rolling_mean_14"]
        
        # Inventory signals (shift to represent state at end of yesterday)
        group["current_inventory"] = group["closing_inventory"].shift(1)
        group["available_inv_sig"] = group["available_inventory"].shift(1)
        
        # Days of inventory based on past demand mean
        group["days_of_inventory"] = group["current_inventory"] / (group["rolling_mean_7"] + 1e-5)
        
        # Target columns: predicting future demand for t+1, t+3, and t+7 days
        # E.g. target_7d is the actual demand observed 7 days into the future (shifted back by -7)
        # For multi-step forecasting, or predicting target windows:
        # We define:
        # future_1d_demand: quantity at t+1
        # future_3d_demand: sum of quantities at t+1, t+2, t+3
        # future_7d_demand: sum of quantities at t+1 to t+7
        
        group["target_1d"] = group["quantity"].shift(-1)
        # Rolling sum of the next 3 days
        group["target_3d"] = group["quantity"].shift(-3).rolling(3).sum()
        # Rolling sum of the next 7 days
        group["target_7d"] = group["quantity"].shift(-7).rolling(7).sum()
        
        features_list.append(group)
        
    df_features = pd.concat(features_list, ignore_index=True)
    
    # Drop rows that don't have lag values (first 28 days of history)
    # If training, also drop rows where target is missing (last 7 days of history)
    if is_training:
        df_features = df_features.dropna(subset=["lag_28", "target_7d"]).reset_index(drop=True)
    else:
        df_features = df_features.dropna(subset=["lag_28"]).reset_index(drop=True)
    
    logger.info(f"Feature matrix built: {df_features.shape[0]} rows, {df_features.shape[1]} columns")
    return df_features
