import os
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from app.core.logging_config import logger

class DemandForecaster:
    """
    Manages training, evaluating, and predicting using baseline and XGBoost models.
    Supports 1-day, 3-day, and 7-day forecasting horizons.
    """
    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        self.models = {}
        
        # Feature definitions
        self.feature_cols = [
            'day_of_week', 'week_of_year', 'month', 'quarter', 'is_weekend',
            'lag_1', 'lag_3', 'lag_7', 'lag_14', 'lag_21', 'lag_28',
            'rolling_mean_7', 'rolling_mean_14', 'rolling_mean_28',
            'rolling_std_7', 'rolling_std_14',
            'recent_demand_growth', 'demand_velocity',
            'current_inventory', 'available_inv_sig', 'days_of_inventory',
            'is_promotional'
        ]

    def load_models(self) -> bool:
        """Loads trained XGBoost models from disk."""
        try:
            for horizon in [1, 3, 7]:
                model_path = os.path.join(self.model_dir, f"xgb_model_{horizon}d.pkl")
                if os.path.exists(model_path):
                    self.models[horizon] = joblib.load(model_path)
                else:
                    logger.warning(f"Model file for {horizon}-day horizon not found.")
                    return False
            logger.info("Forecasting models loaded successfully from disk.")
            return True
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return False

    def save_models(self):
        """Saves models to disk."""
        for horizon, model in self.models.items():
            model_path = os.path.join(self.model_dir, f"xgb_model_{horizon}d.pkl")
            joblib.dump(model, model_path)
            logger.info(f"Model for {horizon}-day horizon saved to {model_path}")

    @staticmethod
    def calculate_wape(y_true, y_pred) -> float:
        """Calculates Weighted Absolute Percentage Error (WAPE)."""
        sum_actual = np.sum(np.abs(y_true))
        if sum_actual == 0:
            return 0.0
        return np.sum(np.abs(y_true - y_pred)) / sum_actual

    @staticmethod
    def calculate_mape(y_true, y_pred) -> float:
        """Calculates Mean Absolute Percentage Error (MAPE)."""
        # Avoid zero division
        mask = y_true != 0
        if not np.any(mask):
            return 0.0
        return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))

    def evaluate(self, y_true, y_pred) -> dict:
        """Calculates standard regression evaluation metrics."""
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        mape = self.calculate_mape(y_true, y_pred)
        wape = self.calculate_wape(y_true, y_pred)
        
        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "mape": float(mape),
            "wape": float(wape),
            "r2": float(r2)
        }

    def train_and_evaluate(self, df_features: pd.DataFrame) -> dict:
        """
        Splits data chronologically and trains XGBoost and baseline models.
        Returns a dictionary of metrics for all horizons and models.
        """
        # Chronological split
        unique_dates = sorted(df_features["date"].unique())
        n_dates = len(unique_dates)
        
        # Split indexes: ~80% train, ~10% val, ~10% test
        train_cutoff = unique_dates[int(n_dates * 0.8)]
        val_cutoff = unique_dates[int(n_dates * 0.9)]
        
        logger.info(f"Splitting data chronologically: train before {train_cutoff}, validation before {val_cutoff}")
        
        train_mask = df_features["date"] < train_cutoff
        val_mask = (df_features["date"] >= train_cutoff) & (df_features["date"] < val_cutoff)
        test_mask = df_features["date"] >= val_cutoff
        
        df_train = df_features[train_mask]
        df_val = df_features[val_mask]
        df_test = df_features[test_mask]
        
        logger.info(f"Train size: {df_train.shape[0]}, Val size: {df_val.shape[0]}, Test size: {df_test.shape[0]}")
        
        results = {}
        
        for horizon in [1, 3, 7]:
            target_col = f"target_{horizon}d"
            logger.info(f"Training models for {horizon}-day horizon target '{target_col}'...")
            
            X_train, y_train = df_train[self.feature_cols], df_train[target_col]
            X_val, y_val = df_val[self.feature_cols], df_val[target_col]
            X_test, y_test = df_test[self.feature_cols], df_test[target_col]
            
            # --- Baseline 1: Naive (forecast = lag_1 for 1d, lag_3 for 3d, lag_7 for 7d)
            # Or simplified: Naive is previous period value
            if horizon == 1:
                naive_test_preds = X_test["lag_1"]
            elif horizon == 3:
                # 3 * lag_1 as baseline
                naive_test_preds = X_test["lag_1"] * 3
            else:
                # 7 * lag_1 as baseline
                naive_test_preds = X_test["lag_1"] * 7
                
            baseline_naive = self.evaluate(y_test, naive_test_preds)
            
            # --- Baseline 2: 7-day Moving Average
            if horizon == 1:
                ma7_test_preds = X_test["rolling_mean_7"]
            elif horizon == 3:
                ma7_test_preds = X_test["rolling_mean_7"] * 3
            else:
                ma7_test_preds = X_test["rolling_mean_7"] * 7
            baseline_ma7 = self.evaluate(y_test, ma7_test_preds)
            
            # --- Baseline 3: 14-day Moving Average
            if horizon == 1:
                ma14_test_preds = X_test["rolling_mean_14"]
            elif horizon == 3:
                ma14_test_preds = X_test["rolling_mean_14"] * 3
            else:
                ma14_test_preds = X_test["rolling_mean_14"] * 7
            baseline_ma14 = self.evaluate(y_test, ma14_test_preds)
            
            # --- Train XGBoost Regressor
            xgb_model = xgb.XGBRegressor(
                n_estimators=150,
                learning_rate=0.08,
                max_depth=5,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1
            )
            
            xgb_model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
            
            # Predict
            test_preds = xgb_model.predict(X_test)
            test_preds = np.clip(test_preds, a_min=0, a_max=None) # Post-processing to avoid negative demand
            
            xgb_metrics = self.evaluate(y_test, test_preds)
            
            # Store trained model
            self.models[horizon] = xgb_model
            
            results[horizon] = {
                "xgb": xgb_metrics,
                "naive": baseline_naive,
                "ma7": baseline_ma7,
                "ma14": baseline_ma14
            }
            
            logger.info(f"{horizon}d XGBoost Test MAE: {xgb_metrics['mae']:.2f}, R2: {xgb_metrics['r2']:.4f}")
            logger.info(f"{horizon}d Naive Baseline Test MAE: {baseline_naive['mae']:.2f}, R2: {baseline_naive['r2']:.4f}")
            
        # Save models
        self.save_models()
        return results

    def predict(self, feature_df: pd.DataFrame, horizon: int = 7) -> np.ndarray:
        """Generates predictions for a specific horizon."""
        if horizon not in self.models:
            loaded = self.load_models()
            if not loaded:
                raise ValueError("Models are not trained or loaded.")
                
        model = self.models[horizon]
        X = feature_df[self.feature_cols]
        preds = model.predict(X)
        return np.clip(preds, a_min=0, a_max=None)
        
    def get_feature_importance(self, horizon: int = 7) -> pd.DataFrame:
        """Returns feature importance list from the trained XGBoost model."""
        if horizon not in self.models:
            self.load_models()
            
        model = self.models.get(horizon)
        if model is None:
            return pd.DataFrame()
            
        importance = model.feature_importances_
        df_imp = pd.DataFrame({
            "feature": self.feature_cols,
            "importance": importance
        }).sort_values(by="importance", ascending=False).reset_index(drop=True)
        return df_imp
