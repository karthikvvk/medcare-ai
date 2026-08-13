import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from app.core.logging_config import logger
from app.models.database_models import SKU, DistributionCenter, InventorySnapshot, Forecast, DemandHistory
from app.core.config import settings

class InventoryService:
    @staticmethod
    def get_average_daily_demand(db: Session, sku_id: str, dc_id: str, current_date: date) -> float:
        """
        Calculates the Average Daily Demand (ADD) using the forecasted 7-day demand.
        Falls back to historical 14-day rolling average if forecast is missing.
        """
        # Attempt to get the latest 7-day forecast
        forecast = db.query(Forecast).filter(
            Forecast.prediction_date == current_date,
            Forecast.sku_id == sku_id,
            Forecast.dc_id == dc_id,
            Forecast.horizon_days == 7
        ).first()
        
        if forecast and forecast.forecasted_demand > 0:
            return max(0.1, forecast.forecasted_demand / 7.0)
            
        # Fallback: historical demand
        history_start = current_date - timedelta(days=14)
        avg_hist = db.query(func.avg(DemandHistory.quantity)).filter(
            DemandHistory.sku_id == sku_id,
            DemandHistory.dc_id == dc_id,
            DemandHistory.date >= history_start,
            DemandHistory.date <= current_date
        ).scalar()
        
        if avg_hist is not None:
            return max(0.1, float(avg_hist))
            
        # Hard fallback to SKU base demand
        sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
        if sku:
            return max(0.1, sku.base_demand)
            
        return 10.0 # Standard fallback

    @staticmethod
    def get_demand_std(db: Session, sku_id: str, dc_id: str, current_date: date) -> float:
        """Calculates standard deviation of historical daily demand over the last 28 days."""
        history_start = current_date - timedelta(days=28)
        demands = db.query(DemandHistory.quantity).filter(
            DemandHistory.sku_id == sku_id,
            DemandHistory.dc_id == dc_id,
            DemandHistory.date >= history_start,
            DemandHistory.date <= current_date
        ).all()
        
        if len(demands) > 1:
            vals = [d[0] for d in demands]
            return float(np.std(vals))
            
        sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
        if sku:
            return sku.base_demand * sku.demand_variability
        return 5.0

    def calculate_safety_stock(self, db: Session, sku_id: str, dc_id: str, current_date: date, service_level: float = None) -> float:
        """
        Calculates safety stock: Z * std_demand * sqrt(lead_time)
        """
        z_score = settings.DEFAULT_Z_SCORE
        if service_level is not None:
            # Map service level to z-score
            if service_level >= 0.99:
                z_score = 2.33
            elif service_level >= 0.95:
                z_score = 1.96
            elif service_level >= 0.90:
                z_score = 1.645
            else:
                z_score = 1.28
                
        # Get lead time
        dc = db.query(DistributionCenter).filter(DistributionCenter.dc_id == dc_id).first()
        lead_time = dc.lead_time_days if dc else settings.DEFAULT_LEAD_TIME_DAYS
        
        std_demand = self.get_demand_std(db, sku_id, dc_id, current_date)
        
        safety_stock = z_score * std_demand * math.sqrt(lead_time)
        return round(safety_stock, 2)

    def calculate_reorder_point(self, db: Session, sku_id: str, dc_id: str, current_date: date, service_level: float = None) -> float:
        """
        Calculates reorder point: (average_daily_demand * lead_time) + safety_stock
        """
        # Average daily demand
        add = self.get_average_daily_demand(db, sku_id, dc_id, current_date)
        
        # Lead time
        dc = db.query(DistributionCenter).filter(DistributionCenter.dc_id == dc_id).first()
        lead_time = dc.lead_time_days if dc else settings.DEFAULT_LEAD_TIME_DAYS
        
        # Safety stock
        ss = self.calculate_safety_stock(db, sku_id, dc_id, current_date, service_level)
        
        rop = (add * lead_time) + ss
        return round(rop, 2)

    def get_inventory_status(self, db: Session, sku_id: str, dc_id: str, current_date: date, service_level: float = None) -> dict:
        """
        Gets detailed inventory metrics for a specific SKU/DC on a specific date.
        """
        sku = db.query(SKU).filter(SKU.sku_id == sku_id).first()
        dc = db.query(DistributionCenter).filter(DistributionCenter.dc_id == dc_id).first()
        
        if not sku or not dc:
            return {}
            
        # Get latest inventory snapshot
        snapshot = db.query(InventorySnapshot).filter(
            InventorySnapshot.sku_id == sku_id,
            InventorySnapshot.dc_id == dc_id,
            InventorySnapshot.date == current_date
        ).first()
        
        if not snapshot:
            # Fallback to the latest available snapshot
            snapshot = db.query(InventorySnapshot).filter(
                InventorySnapshot.sku_id == sku_id,
                InventorySnapshot.dc_id == dc_id,
                InventorySnapshot.date <= current_date
            ).order_by(InventorySnapshot.date.desc()).first()
            
        closing_inv = snapshot.closing_inventory if snapshot else 0.0
        available_inv = snapshot.available_inventory if snapshot else 0.0
        incoming_inv = snapshot.incoming_inventory if snapshot else 0.0
        
        add = self.get_average_daily_demand(db, sku_id, dc_id, current_date)
        doi = available_inv / add if add > 0 else 0.0
        
        ss = self.calculate_safety_stock(db, sku_id, dc_id, current_date, service_level)
        rop = self.calculate_reorder_point(db, sku_id, dc_id, current_date, service_level)
        
        # Forecasted demand for the next 7 days
        fc_7d = db.query(Forecast).filter(
            Forecast.prediction_date == current_date,
            Forecast.sku_id == sku_id,
            Forecast.dc_id == dc_id,
            Forecast.horizon_days == 7
        ).first()
        forecast_qty = fc_7d.forecasted_demand if fc_7d else add * 7.0
        
        inventory_gap = max(0.0, forecast_qty - available_inv)
        
        return {
            "sku_id": sku_id,
            "sku_name": sku.name,
            "dc_id": dc_id,
            "dc_name": dc.name,
            "closing_inventory": closing_inv,
            "available_inventory": available_inv,
            "incoming_inventory": incoming_inv,
            "average_daily_demand": round(add, 2),
            "days_of_inventory": round(doi, 2),
            "safety_stock": ss,
            "reorder_point": rop,
            "lead_time_days": dc.lead_time_days,
            "forecast_7d": round(forecast_qty, 2),
            "inventory_gap": round(inventory_gap, 2),
            "unit_cost": sku.unit_cost,
            "value": round(closing_inv * sku.unit_cost, 2),
            "criticality": sku.criticality
        }
