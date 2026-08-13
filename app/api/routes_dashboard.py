from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import List
from app.core.database import get_db
from app.models.database_models import SKU, DistributionCenter, ModelMetric, Forecast, Recommendation, Transfer
from app.models.schemas import SKUResponse, DCResponse, ModelMetricResponse
from app.services.explanation_service import ExplanationService

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Core Data"])
explanation_service = ExplanationService()

@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "MedCare Supply Chain Intelligence"}

@router.get("/skus", response_model=List[SKUResponse])
def get_skus(db: Session = Depends(get_db)):
    return db.query(SKU).all()

@router.get("/distribution-centers", response_model=List[DCResponse])
def get_dcs(db: Session = Depends(get_db)):
    return db.query(DistributionCenter).all()

@router.get("/model-metrics", response_model=List[ModelMetricResponse])
def get_model_metrics(db: Session = Depends(get_db)):
    return db.query(ModelMetric).all()

@router.get("/summary")
def get_executive_summary(
    date_str: str = Query("2026-08-12", description="Current date in ISO format (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    summary_text = explanation_service.generate_executive_summary(db, current_date)
    
    # Calculate some quick overview counters
    total_recs = db.query(Recommendation).count()
    critical_recs = db.query(Recommendation).filter(Recommendation.priority == "CRITICAL").count()
    high_recs = db.query(Recommendation).filter(Recommendation.priority == "HIGH").count()
    transfers_count = db.query(Transfer).filter(Transfer.status == "RECOMMENDED").count()
    replenish_count = db.query(Recommendation).filter(Recommendation.action_type == "REPLENISH").count()
    
    # Calculate approximate inventory accuracy & service levels based on synthetic data
    # (Since this is a demo, we aggregate from the demand and inventory histories)
    # Lost sales rate, stockout occurrences
    return {
        "summary": summary_text,
        "counters": {
            "total_actions": total_recs,
            "critical_risks": critical_recs,
            "high_risks": high_recs,
            "replenishment_orders": replenish_count,
            "transfers": transfers_count
        }
    }
