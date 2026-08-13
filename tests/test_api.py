import pytest
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "MedCare Pharma" in response.text

def test_api_health():
    response = client.get("/api/dashboard/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_update_recommendation_status_not_found():
    response = client.post("/api/recommendations/non_existent_id/status?status=APPROVED")
    assert response.status_code == 404
