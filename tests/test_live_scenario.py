import pytest
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_get_live_scenario_status():
    response = client.get("/api/live-scenario/status?date_str=2026-08-12")
    assert response.status_code == 200
    data = response.json()
    assert "active_scenario" in data
    assert "ollama_status" in data
    assert "event" in data["active_scenario"]
    assert "region" in data["active_scenario"]

def test_set_simulation():
    # Test setting custom simulation
    payload = {
        "event": "Flood",
        "region": "Chennai",
        "area": "Velachery",
        "severity": "High"
    }
    response = client.post("/api/live-scenario/simulate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify status changed to simulation
    status_response = client.get("/api/live-scenario/status?date_str=2026-08-12")
    assert status_response.status_code == 200
    active_sc = status_response.json()["active_scenario"]
    assert active_sc["event"] == "Flood"
    assert active_sc["region"] == "Chennai"
    assert active_sc["area"] == "Velachery"
    assert active_sc["severity"] == "High"
    assert active_sc["is_simulated"] is True

def test_reset_simulation():
    # Reset simulation
    response = client.post("/api/live-scenario/reset")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify status reverted to auto-detected
    status_response = client.get("/api/live-scenario/status?date_str=2026-08-12")
    assert status_response.status_code == 200
    active_sc = status_response.json()["active_scenario"]
    assert active_sc["is_simulated"] is False

def test_run_analysis():
    # Test analysis endpoint runs successfully (even in fallback mode)
    response = client.post("/api/live-scenario/analyze?date_str=2026-08-12")
    assert response.status_code == 200
    data = response.json()
    assert "active_scenario" in data
    assert "health_risks" in data
    assert "region_recommendations" in data
    assert "analysis_mode" in data
    assert len(data["region_recommendations"]) > 0

    # Test that we can commit recommendations
    commit_response = client.post("/api/live-scenario/commit")
    assert commit_response.status_code == 200
    assert commit_response.json()["status"] == "success"

def test_ollama_status_and_pull():
    response = client.get("/api/live-scenario/ollama-status")
    assert response.status_code == 200
    assert "is_connected" in response.json()

    pull_response = client.post("/api/live-scenario/ollama-pull")
    assert pull_response.status_code == 200
    assert pull_response.json()["status"] == "success"
