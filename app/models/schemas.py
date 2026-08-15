from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

class SKUBase(BaseModel):
    sku_id: str
    name: str
    category: str
    therapeutic_class: str
    unit_cost: float
    criticality: str
    shelf_life_days: int
    base_demand: float
    demand_variability: float
    min_order_qty: int

class SKUResponse(SKUBase):
    class Config:
        from_attributes = True

class DCBase(BaseModel):
    dc_id: str
    name: str
    location: str
    region: str
    storage_capacity: int
    lead_time_days: int
    service_priority: int

class DCResponse(DCBase):
    class Config:
        from_attributes = True

class ForecastBase(BaseModel):
    prediction_date: date
    sku_id: str
    dc_id: str
    forecast_date: date
    forecasted_demand: float
    horizon_days: int
    confidence_score: float

class ForecastResponse(ForecastBase):
    id: int
    class Config:
        from_attributes = True

class InventorySnapshotBase(BaseModel):
    date: date
    sku_id: str
    dc_id: str
    opening_inventory: float
    incoming_inventory: float
    outgoing_inventory: float
    closing_inventory: float
    reserved_inventory: float
    available_inventory: float

class InventorySnapshotResponse(InventorySnapshotBase):
    id: int
    class Config:
        from_attributes = True

class BatchBase(BaseModel):
    batch_id: str
    sku_id: str
    dc_id: str
    manufacturing_date: date
    expiry_date: date
    initial_quantity: float
    remaining_quantity: float

class BatchResponse(BatchBase):
    class Config:
        from_attributes = True

class RecommendationBase(BaseModel):
    recommendation_id: str
    timestamp: datetime
    sku_id: str
    dc_id: str
    action_type: str
    quantity: float
    priority: str
    reason: str
    expected_impact: str
    confidence: float
    status: str

class RecommendationResponse(RecommendationBase):
    class Config:
        from_attributes = True

class TransferBase(BaseModel):
    transfer_id: str
    recommendation_id: Optional[str]
    sku_id: str
    source_dc_id: str
    destination_dc_id: str
    batch_id: str
    quantity: float
    transit_days: int
    status: str

class TransferResponse(TransferBase):
    class Config:
        from_attributes = True

class ModelMetricBase(BaseModel):
    model_name: str
    eval_date: date
    mae: float
    rmse: float
    mape: float
    wape: float
    r2: float

class ModelMetricResponse(ModelMetricBase):
    class Config:
        from_attributes = True

# Simulation input
class SimulationRequest(BaseModel):
    demand_increase_pct: float = Field(0.0, ge=0.0, le=100.0)
    promotion_impact_pct: float = Field(0.0, ge=0.0, le=100.0)
    supplier_lead_time_days_offset: int = Field(0, ge=-10, le=10)
    inventory_reduction_pct: float = Field(0.0, ge=0.0, le=90.0)
    seasonality_multiplier: float = Field(1.0, ge=0.1, le=5.0)

# Simulation output
class SimulationResultSummary(BaseModel):
    sku_id: str
    dc_id: str
    original_stockout_risk: str
    simulated_stockout_risk: str
    original_replenish_qty: float
    simulated_replenish_qty: float
    original_expiry_risk: str
    simulated_expiry_risk: str
    reason: str

class SimulationResponse(BaseModel):
    original_stockout_events: int
    simulated_stockout_events: int
    original_expiry_risks: int
    simulated_expiry_risks: int
    additional_replenishment_units: float
    details: List[SimulationResultSummary]
