from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional
from app.core.database import get_db
from app.models.database_models import Forecast, DemandHistory
from app.models.schemas import ForecastResponse

router = APIRouter(prefix="/forecast", tags=["Demand Forecasting"])

@router.post("/generate")
def generate_forecasts(
    prediction_date: str = Query(..., description="Date of forecast prediction in YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    try:
        pred_date = date.fromisoformat(prediction_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    from app.services.forecasting_service import ForecastingService
    fs = ForecastingService()
    forecasts = fs.generate_and_save_forecasts(db, pred_date)
    return {"message": "Forecasts generated successfully", "count": len(forecasts)}

@router.get("", response_model=List[ForecastResponse])
def get_forecasts(
    prediction_date: str = Query(..., description="Date of forecast prediction in YYYY-MM-DD"),
    sku_id: Optional[str] = Query(None),
    dc_id: Optional[str] = Query(None),
    horizon_days: Optional[int] = Query(None, description="Forecast horizon (1, 3, 7)"),
    db: Session = Depends(get_db)
):
    try:
        pred_date = date.fromisoformat(prediction_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    query = db.query(Forecast).filter(Forecast.prediction_date == pred_date)
    
    if sku_id:
        query = query.filter(Forecast.sku_id == sku_id)
    if dc_id:
        query = query.filter(Forecast.dc_id == dc_id)
    if horizon_days:
        query = query.filter(Forecast.horizon_days == horizon_days)
        
    return query.all()

@router.get("/historical-comparison")
def get_forecast_comparison(
    prediction_date: str = Query(..., description="Date of prediction (YYYY-MM-DD)"),
    sku_id: str = Query(...),
    dc_id: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        pred_date = date.fromisoformat(prediction_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    # Get historical actuals for 14 days before and 7 days after pred_date
    history_start = pred_date - date.resolution * 14
    history_end = pred_date + date.resolution * 7
    
    actuals = db.query(DemandHistory).filter(
        DemandHistory.sku_id == sku_id,
        DemandHistory.dc_id == dc_id,
        DemandHistory.date >= history_start,
        DemandHistory.date <= history_end
    ).order_by(DemandHistory.date.asc()).all()
    
    # Get forecasts made on pred_date
    forecasts = db.query(Forecast).filter(
        Forecast.prediction_date == pred_date,
        Forecast.sku_id == sku_id,
        Forecast.dc_id == dc_id
    ).all()
    
    # Serialize actuals
    hist_list = [{"date": a.date.isoformat(), "actual": a.quantity} for a in actuals]
    
    # Serialize forecasts
    fc_list = []
    for f in forecasts:
        fc_list.append({
            "forecast_date": f.forecast_date.isoformat(),
            "forecast": f.forecasted_demand,
            "horizon": f.horizon_days,
            "confidence": f.confidence_score
        })
        
    return {
        "actuals": hist_list,
        "forecasts": fc_list
    }
