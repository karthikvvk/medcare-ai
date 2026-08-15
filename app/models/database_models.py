from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Boolean, ForeignKey, Table, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class SKU(Base):
    __tablename__ = 'skus'
    
    sku_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    therapeutic_class = Column(String(100), nullable=False)
    unit_cost = Column(Float, nullable=False)
    criticality = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    shelf_life_days = Column(Integer, nullable=False)
    base_demand = Column(Float, nullable=False)
    demand_variability = Column(Float, nullable=False)
    min_order_qty = Column(Integer, default=100)

    # Relationships
    batches = relationship("Batch", back_populates="sku")
    demand_history = relationship("DemandHistory", back_populates="sku")
    inventory_snapshots = relationship("InventorySnapshot", back_populates="sku")
    orders = relationship("DistributorOrder", back_populates="sku")
    forecasts = relationship("Forecast", back_populates="sku")
    recommendations = relationship("Recommendation", back_populates="sku")
    transfers = relationship("Transfer", back_populates="sku")


class DistributionCenter(Base):
    __tablename__ = 'distribution_centers'
    
    dc_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    location = Column(String(100), nullable=False)
    region = Column(String(50), nullable=False)
    storage_capacity = Column(Integer, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    service_priority = Column(Integer, default=3)

    # Relationships
    batches = relationship("Batch", back_populates="dc")
    demand_history = relationship("DemandHistory", back_populates="dc")
    inventory_snapshots = relationship("InventorySnapshot", back_populates="dc")
    orders = relationship("DistributorOrder", back_populates="dc")
    forecasts = relationship("Forecast", back_populates="dc")
    recommendations = relationship("Recommendation", back_populates="dc")


class Supplier(Base):
    __tablename__ = 'suppliers'
    
    supplier_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    reliability_score = Column(Float, default=0.95)


class SKU_Supplier(Base):
    __tablename__ = 'sku_suppliers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    supplier_id = Column(String(50), ForeignKey('suppliers.supplier_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    lead_time_days = Column(Integer, nullable=False)


class Promotion(Base):
    __tablename__ = 'promotions'
    
    promotion_id = Column(String(50), primary_key=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    promotion_type = Column(String(50), nullable=False)
    discount_percentage = Column(Float, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)


class DemandHistory(Base):
    __tablename__ = 'demand_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    quantity = Column(Float, nullable=False)
    is_promotional = Column(Boolean, default=False)
    out_of_stock_lost_sales = Column(Float, default=0.0)

    sku = relationship("SKU", back_populates="demand_history")
    dc = relationship("DistributionCenter", back_populates="demand_history")


class DistributorOrder(Base):
    __tablename__ = 'distributor_orders'
    
    order_id = Column(String(50), primary_key=True)
    order_date = Column(Date, nullable=False, index=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    ordered_quantity = Column(Float, nullable=False)
    fulfilled_quantity = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)  # PENDING, FULFILLED, PARTIAL, CANCELLED

    sku = relationship("SKU", back_populates="orders")
    dc = relationship("DistributionCenter", back_populates="orders")


class InventorySnapshot(Base):
    __tablename__ = 'inventory_snapshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    opening_inventory = Column(Float, nullable=False)
    incoming_inventory = Column(Float, default=0.0)
    outgoing_inventory = Column(Float, default=0.0)
    closing_inventory = Column(Float, nullable=False)
    reserved_inventory = Column(Float, default=0.0)
    available_inventory = Column(Float, nullable=False)

    sku = relationship("SKU", back_populates="inventory_snapshots")
    dc = relationship("DistributionCenter", back_populates="inventory_snapshots")


class Batch(Base):
    __tablename__ = 'batches'
    
    batch_id = Column(String(50), primary_key=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    manufacturing_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    initial_quantity = Column(Float, nullable=False)
    remaining_quantity = Column(Float, nullable=False)

    sku = relationship("SKU", back_populates="batches")
    dc = relationship("DistributionCenter", back_populates="batches")
    transfers = relationship("Transfer", back_populates="batch")


class Forecast(Base):
    __tablename__ = 'forecasts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_date = Column(Date, nullable=False, index=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    forecast_date = Column(Date, nullable=False)
    forecasted_demand = Column(Float, nullable=False)
    horizon_days = Column(Integer, nullable=False)  # 1, 3, 7
    confidence_score = Column(Float, nullable=False)

    sku = relationship("SKU", back_populates="forecasts")
    dc = relationship("DistributionCenter", back_populates="forecasts")


class Recommendation(Base):
    __tablename__ = 'recommendations'
    
    recommendation_id = Column(String(50), primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    action_type = Column(String(30), nullable=False)  # NO_ACTION, REPLENISH, TRANSFER, EXPEDITE, REDUCE_ORDER, MONITOR
    quantity = Column(Float, nullable=False)
    priority = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    reason = Column(Text, nullable=False)
    expected_impact = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED, EXECUTED

    sku = relationship("SKU", back_populates="recommendations")
    dc = relationship("DistributionCenter", back_populates="recommendations")
    transfers = relationship("Transfer", back_populates="recommendation")


class Transfer(Base):
    __tablename__ = 'transfers'
    
    transfer_id = Column(String(50), primary_key=True)
    recommendation_id = Column(String(50), ForeignKey('recommendations.recommendation_id'), nullable=True)
    sku_id = Column(String(50), ForeignKey('skus.sku_id'), nullable=False)
    source_dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    destination_dc_id = Column(String(50), ForeignKey('distribution_centers.dc_id'), nullable=False)
    batch_id = Column(String(50), ForeignKey('batches.batch_id'), nullable=False)
    quantity = Column(Float, nullable=False)
    transit_days = Column(Integer, nullable=False)
    status = Column(String(20), default="RECOMMENDED")  # RECOMMENDED, IN_TRANSIT, COMPLETED

    sku = relationship("SKU", back_populates="transfers")
    batch = relationship("Batch", back_populates="transfers")
    recommendation = relationship("Recommendation", back_populates="transfers")
    
    # Custom DC relationship naming to resolve ambiguity
    source_dc = relationship("DistributionCenter", foreign_keys=[source_dc_id])
    destination_dc = relationship("DistributionCenter", foreign_keys=[destination_dc_id])


class ModelMetric(Base):
    __tablename__ = 'model_metrics'
    
    model_name = Column(String(100), primary_key=True)
    eval_date = Column(Date, primary_key=True)
    mae = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    mape = Column(Float, nullable=False)
    wape = Column(Float, nullable=False)
    r2 = Column(Float, nullable=False)
