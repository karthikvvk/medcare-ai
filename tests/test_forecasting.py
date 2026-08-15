import pytest
import pandas as pd
import numpy as np
from datetime import date
from app.models.forecasting import DemandForecaster

def test_wape_calculation():
    forecaster = DemandForecaster()
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 33.0])
    
    # |10-12| + |20-18| + |30-33| = 2 + 2 + 3 = 7
    # 7 / (10+20+30) = 7/60 = 0.1167
    wape = forecaster.calculate_wape(y_true, y_pred)
    assert pytest.approx(wape, 0.0001) == 0.116666

def test_mape_calculation():
    forecaster = DemandForecaster()
    y_true = np.array([10.0, 20.0, 0.0])  # zero value handled
    y_pred = np.array([12.0, 18.0, 5.0])
    
    # |10-12|/10 = 0.2
    # |20-18|/20 = 0.1
    # Average of 0.2 and 0.1 is 0.15
    mape = forecaster.calculate_mape(y_true, y_pred)
    assert pytest.approx(mape, 0.0001) == 0.15
