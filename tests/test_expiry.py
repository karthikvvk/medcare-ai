import pytest
from datetime import date, timedelta

def test_fefo_expiry_simulation_logic():
    # Chennai has a batch of 500 expiring in 20 days.
    # Daily demand is 30.
    # Demand during remaining 20 days is 30 * 20 = 600.
    # Projected waste is max(0, 500 - 600) = 0. Expiry risk = low/safe.
    
    qty = 500.0
    days_to_exp = 20
    add = 30.0
    
    ecd = add * days_to_exp
    waste = max(0.0, qty - ecd)
    assert waste == 0.0
    
    # What if demand was only 10?
    # Demand during 20 days = 10 * 20 = 200.
    # Waste = max(0, 500 - 200) = 300. Expiry risk = high.
    add = 10.0
    ecd = add * days_to_exp
    waste = max(0.0, qty - ecd)
    assert waste == 300.0
