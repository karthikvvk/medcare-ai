import pytest
import math
from app.services.inventory_service import InventoryService

def test_safety_stock_formula_manually():
    # safety_stock = Z * std_demand * sqrt(lead_time)
    # Z = 1.96 (for 95% service level)
    # std_demand = 10.0
    # lead_time = 4
    # ss = 1.96 * 10.0 * sqrt(4) = 1.96 * 10.0 * 2 = 39.2
    
    z = 1.96
    std = 10.0
    lt = 4
    ss = z * std * math.sqrt(lt)
    assert ss == 39.2
