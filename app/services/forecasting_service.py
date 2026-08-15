import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.models.forecasting import DemandForecaster
from app.models.database_models import Forecast, DemandHistory, InventorySnapshot, SKU, DistributionCenter
from app.data.preprocessing import build_features

class ForecastingService:
    def __init__(self):
        self.forecaster = DemandForecaster()
        self.models_loaded = self.forecaster.load_models()

    def generate_and_save_forecasts(self, db: Session, target_date: date):
        """
        Generates 1-day, 3-day, and 7-day forecasts for all SKU-DC combinations
        at a specific target date (representing the 'current' date in operation)
        and saves them to the forecasts table.
        """
        logger.info(f"Generating forecasts for target_date={target_date}...")
        
        # 1. Fetch historical demand and inventory snapshots up to target_date
        # We need at least the last 28 days of history for feature calculation
        history_start = target_date - timedelta(days=45)
        
        db_demand = db.query(DemandHistory).filter(DemandHistory.date >= history_start, DemandHistory.date <= target_date).all()
        db_inv = db.query(InventorySnapshot).filter(InventorySnapshot.date >= history_start, InventorySnapshot.date <= target_date).all()
        
        if not db_demand or not db_inv:
            logger.warning("Insufficient historical data to generate features for forecasting.")
            return []
            
        # Convert to dataframes
        df_demand = pd.DataFrame([{
            "date": d.date, "sku_id": d.sku_id, "dc_id": d.dc_id,
            "quantity": d.quantity, "is_promotional": d.is_promotional,
            "out_of_stock_lost_sales": d.out_of_stock_lost_sales
        } for d in db_demand])
        
        df_inv = pd.DataFrame([{
            "date": i.date, "sku_id": i.sku_id, "dc_id": i.dc_id,
            "opening_inventory": i.opening_inventory, "incoming_inventory": i.incoming_inventory,
            "outgoing_inventory": i.outgoing_inventory, "closing_inventory": i.closing_inventory,
            "reserved_inventory": i.reserved_inventory, "available_inventory": i.available_inventory
        } for i in db_inv])
        
        # --- Append prediction-date placeholder rows to compute features ---
        # Get unique SKU/DC combinations
        combos = df_demand[["sku_id", "dc_id"]].drop_duplicates()
        
        new_demands = []
        new_inventories = []
        
        for _, r in combos.iterrows():
            s_id = r["sku_id"]
            d_id = r["dc_id"]
            
            # Append demand placeholder
            new_demands.append({
                "date": target_date,
                "sku_id": s_id,
                "dc_id": d_id,
                "quantity": 0.0,
                "is_promotional": False,
                "out_of_stock_lost_sales": 0.0
            })
            
            # Find yesterday's inventory
            yesterday_inv = df_inv[(df_inv["sku_id"] == s_id) & (df_inv["dc_id"] == d_id)]
            if not yesterday_inv.empty:
                last_row = yesterday_inv.sort_values(by="date").iloc[-1]
                closing = last_row["closing_inventory"]
                avail = last_row["available_inventory"]
                incoming = last_row["incoming_inventory"]
            else:
                closing, avail, incoming = 100.0, 90.0, 0.0
                
            new_inventories.append({
                "date": target_date,
                "sku_id": s_id,
                "dc_id": d_id,
                "opening_inventory": closing,
                "incoming_inventory": incoming,
                "outgoing_inventory": 0.0,
                "closing_inventory": closing,
                "reserved_inventory": closing - avail,
                "available_inventory": avail
            })
            
        df_demand = pd.concat([df_demand, pd.DataFrame(new_demands)], ignore_index=True)
        df_inv = pd.concat([df_inv, pd.DataFrame(new_inventories)], ignore_index=True)
        
        # Build features
        # Note: build_features naturally computes target columns, but here we only need features at target_date
        df_feat = build_features(df_demand, df_inv, is_training=False)
        
        # Filter for only the row corresponding to target_date
        df_feat["date"] = pd.to_datetime(df_feat["date"])
        target_datetime = pd.to_datetime(target_date)
        df_today = df_feat[df_feat["date"] == target_datetime]
        
        if df_today.empty:
            logger.warning(f"No feature records generated for date {target_date}.")
            return []
            
        # 2. Run prediction
        forecasts_to_save = []
        
        # Clear old forecasts for this prediction date
        db.query(Forecast).filter(Forecast.prediction_date == target_date).delete()
        
        for _, row in df_today.iterrows():
            sku_id = row["sku_id"]
            dc_id = row["dc_id"]
            
            # Predict for 1, 3, and 7 days
            pred_1d = float(self.forecaster.predict(pd.DataFrame([row]), horizon=1)[0])
            pred_3d = float(self.forecaster.predict(pd.DataFrame([row]), horizon=3)[0])
            pred_7d = float(self.forecaster.predict(pd.DataFrame([row]), horizon=7)[0])
            
            # Fetch SKU details to get demand_variability
            sku_obj = db.query(SKU).filter(SKU.sku_id == sku_id).first()
            var = sku_obj.demand_variability if sku_obj else 0.25
            
            # Generate confidence score (based on moving average variance heuristic or set high default)
            confidence = 0.95 - (var * 0.3) # Critical/volatile SKUs get lower confidence
            confidence = float(np.clip(confidence, 0.6, 0.98))
            
            # Save 1d
            forecasts_to_save.append(Forecast(
                prediction_date=target_date,
                sku_id=sku_id,
                dc_id=dc_id,
                forecast_date=target_date + timedelta(days=1),
                forecasted_demand=pred_1d,
                horizon_days=1,
                confidence_score=confidence
            ))
            # Save 3d
            forecasts_to_save.append(Forecast(
                prediction_date=target_date,
                sku_id=sku_id,
                dc_id=dc_id,
                forecast_date=target_date + timedelta(days=3),
                forecasted_demand=pred_3d,
                horizon_days=3,
                confidence_score=confidence
            ))
            # Save 7d
            forecasts_to_save.append(Forecast(
                prediction_date=target_date,
                sku_id=sku_id,
                dc_id=dc_id,
                forecast_date=target_date + timedelta(days=7),
                forecasted_demand=pred_7d,
                horizon_days=7,
                confidence_score=confidence
            ))
            
        logger.info(f"Generated {len(forecasts_to_save)} forecasts.")
        
        # Save the predicted outputs to output.db as requested
        try:
            import sqlite3
            df_out = pd.DataFrame([{
                "prediction_date": f.prediction_date,
                "sku_id": f.sku_id,
                "dc_id": f.dc_id,
                "forecast_date": f.forecast_date,
                "forecasted_demand": f.forecasted_demand,
                "horizon_days": f.horizon_days,
                "confidence_score": f.confidence_score
            } for f in forecasts_to_save])
            conn = sqlite3.connect('output.db')
            
            table_name = datetime.now().strftime('%Y-%m-%d_%H')
            df_out.to_sql(table_name, conn, if_exists='replace', index=False)
            conn.close()
            logger.info(f"Saved predicted outputs to output.db in table {table_name}")
        except Exception as e:
            logger.error(f"Failed to save to output.db: {e}")
            
        return forecasts_to_save
        
    def generate_single_forecast(self, sku_id: str, dc_id: str, current_stock: float, hist_demand: list, is_promotional: bool = False, sim_multiplier: float = 1.0) -> dict:
        """
        Generates simulated forecasts on the fly for simulation / dashboard what-if checks.
        Allows passing history as a list of daily values.
        """
        # If models not loaded, use MA7/14 heuristics as fallback
        # Pre-process inputs to form a single-row feature dataframe
        hist_len = len(hist_demand)
        if hist_len < 28:
            # Fallback to simple averages if history is short
            base_dem = np.mean(hist_demand) if hist_len > 0 else 50.0
            pred_1d = base_dem * sim_multiplier
            pred_3d = base_dem * 3 * sim_multiplier
            pred_7d = base_dem * 7 * sim_multiplier
            return {
                "forecast_1d": round(pred_1d, 2),
                "forecast_3d": round(pred_3d, 2),
                "forecast_7d": round(pred_7d, 2),
                "confidence_score": 0.80
            }
            
        # Calculate features manually
        rolling_mean_7 = np.mean(hist_demand[-7:])
        rolling_mean_14 = np.mean(hist_demand[-14:])
        rolling_mean_28 = np.mean(hist_demand[-28:])
        rolling_std_7 = np.std(hist_demand[-7:])
        rolling_std_14 = np.std(hist_demand[-14:])
        
        row = {
            'day_of_week': date.today().weekday(),
            'week_of_year': date.today().isocalendar()[1],
            'month': date.today().month,
            'quarter': (date.today().month - 1) // 3 + 1,
            'is_weekend': 1 if date.today().weekday() in [5, 6] else 0,
            'lag_1': hist_demand[-1],
            'lag_3': hist_demand[-3],
            'lag_7': hist_demand[-7],
            'lag_14': hist_demand[-14],
            'lag_21': hist_demand[-21],
            'lag_28': hist_demand[-28],
            'rolling_mean_7': rolling_mean_7,
            'rolling_mean_14': rolling_mean_14,
            'rolling_mean_28': rolling_mean_28,
            'rolling_std_7': rolling_std_7,
            'rolling_std_14': rolling_std_14,
            'recent_demand_growth': rolling_mean_7 / (rolling_mean_28 + 1e-5),
            'demand_velocity': rolling_mean_7 - rolling_mean_14,
            'current_inventory': current_stock,
            'available_inv_sig': current_stock * 0.9,
            'days_of_inventory': current_stock / (rolling_mean_7 + 1e-5),
            'is_promotional': 1 if is_promotional else 0
        }
        
        df_single = pd.DataFrame([row])
        
        try:
            pred_1d = float(self.forecaster.predict(df_single, horizon=1)[0]) * sim_multiplier
            pred_3d = float(self.forecaster.predict(df_single, horizon=3)[0]) * sim_multiplier
            pred_7d = float(self.forecaster.predict(df_single, horizon=7)[0]) * sim_multiplier
        except Exception as e:
            # Heuristic fallback
            logger.warning(f"Error executing XGBoost prediction in simulation: {e}. Falling back to heuristics.")
            pred_1d = rolling_mean_7 * sim_multiplier
            pred_3d = rolling_mean_7 * 3 * sim_multiplier
            pred_7d = rolling_mean_7 * 7 * sim_multiplier
            
        return {
            "forecast_1d": round(max(0.0, pred_1d), 2),
            "forecast_3d": round(max(0.0, pred_3d), 2),
            "forecast_7d": round(max(0.0, pred_7d), 2),
            "confidence_score": 0.85
        }
