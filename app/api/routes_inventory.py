from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
from app.core.database import get_db
from app.services.inventory_service import InventoryService
from app.services.risk_service import RiskService
from app.services.expiry_service import ExpiryService
from app.models.database_models import SKU, DistributionCenter

router = APIRouter(prefix="/inventory", tags=["Inventory & Risks"])
inventory_service = InventoryService()
risk_service = RiskService()
expiry_service = ExpiryService()

@router.get("/status")
def get_inventory_status(
    date_str: str = Query(..., description="Date of inventory snapshot (YYYY-MM-DD)"),
    sku_id: Optional[str] = Query(None),
    dc_id: Optional[str] = Query(None),
    service_level: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    skus_query = db.query(SKU)
    if sku_id:
        skus_query = skus_query.filter(SKU.sku_id == sku_id)
    skus = skus_query.all()
    
    dcs_query = db.query(DistributionCenter)
    if dc_id:
        dcs_query = dcs_query.filter(DistributionCenter.dc_id == dc_id)
    dcs = dcs_query.all()
    
    results = []
    for s in skus:
        for d in dcs:
            status = inventory_service.get_inventory_status(db, s.sku_id, d.dc_id, current_date, service_level)
            if status:
                results.append(status)
                
    return results

@router.get("/stockout-risks")
def get_stockout_risks(
    date_str: str = Query(..., description="Date of evaluation (YYYY-MM-DD)"),
    sku_id: Optional[str] = Query(None),
    dc_id: Optional[str] = Query(None),
    service_level: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    skus_query = db.query(SKU)
    if sku_id:
        skus_query = skus_query.filter(SKU.sku_id == sku_id)
    skus = skus_query.all()
    
    dcs_query = db.query(DistributionCenter)
    if dc_id:
        dcs_query = dcs_query.filter(DistributionCenter.dc_id == dc_id)
    dcs = dcs_query.all()
    
    results = []
    for s in skus:
        for d in dcs:
            risk = risk_service.evaluate_stockout_risk(db, s.sku_id, d.dc_id, current_date, service_level)
            if risk:
                results.append(risk)
                
    return results

@router.get("/expiry-risks")
def get_expiry_risks(
    date_str: str = Query(..., description="Date of evaluation (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    reports = expiry_service.simulate_fefo_expiry_risks(db, current_date)
    return reports
