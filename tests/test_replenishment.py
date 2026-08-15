import pytest

def test_replenishment_quantity_moq():
    # Target inventory = 520
    # Available = 100, Incoming = 200
    # Net requirement = 520 - 100 - 200 = 220
    # MOQ = 100
    # Mapped replenishment = ceil(220 / 100) * 100 = 300
    
    target = 520.0
    avail = 100.0
    incoming = 200.0
    moq = 100.0
    
    req = target - avail - incoming
    recommended = max(0.0, req)
    
    if recommended > 0:
        recommended = float(import_ceil(recommended / moq) * moq)
        
    assert recommended == 300.0

def import_ceil(x):
    import math
    return math.ceil(x)
