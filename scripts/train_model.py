import sys
import os
import pandas as pd
from datetime import datetime

# Adjust path to enable importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging_config import logger
from app.data.preprocessing import clean_raw_data, build_features
from app.models.forecasting import DemandForecaster
from app.core.database import SessionLocal, engine
from app.models.database_models import Base, ModelMetric

def main():
    logger.info("Initializing model training pipeline...")
    
    # 1. Clean data
    clean_raw_data()
    
    # 2. Build features
    df_features = build_features()
    
    # 3. Train models
    forecaster = DemandForecaster()
    results = forecaster.train_and_evaluate(df_features)
    
    # 4. Save metrics to database
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Delete old metrics
        db.query(ModelMetric).delete()
        
        for horizon, metrics_map in results.items():
            for m_name, metrics in metrics_map.items():
                db_metric = ModelMetric(
                    model_name=f"XGBoost_{horizon}d" if m_name == "xgb" else f"{m_name.upper()}_{horizon}d",
                    eval_date=datetime.now().date(),
                    mae=metrics["mae"],
                    rmse=metrics["rmse"],
                    mape=metrics["mape"],
                    wape=metrics["wape"],
                    r2=metrics["r2"]
                )
                db.add(db_metric)
        db.commit()
        logger.info("Saved model evaluation metrics to database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving metrics to DB: {e}")
    finally:
        db.close()
        
    print("\n" + "="*50)
    print("MODEL EVALUATION METRICS:")
    print("="*50)
    for horizon in [1, 3, 7]:
        print(f"\n--- {horizon}-day Horizon ---")
        xgb_m = results[horizon]["xgb"]
        naive_m = results[horizon]["naive"]
        print(f"XGBoost  - MAE: {xgb_m['mae']:.2f}, RMSE: {xgb_m['rmse']:.2f}, WAPE: {xgb_m['wape']:.4f}, R2: {xgb_m['r2']:.4f}")
        print(f"Naive    - MAE: {naive_m['mae']:.2f}, RMSE: {naive_m['rmse']:.2f}, WAPE: {naive_m['wape']:.4f}, R2: {naive_m['r2']:.4f}")
    print("="*50 + "\n")
    logger.info("Model training pipeline finished successfully!")

if __name__ == "__main__":
    main()
