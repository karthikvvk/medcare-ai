from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from datetime import date
from app.core.database import get_db
from app.services.live_scenario_service import LiveScenarioService, OllamaManager
from app.core.config import settings

router = APIRouter(prefix="/live-scenario", tags=["Live AI Scenario Analysis"])
service = LiveScenarioService()

@router.get("/status")
def get_scenario_status(date_str: str = Query(..., description="Evaluation date YYYY-MM-DD"), db: Session = Depends(get_db)):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    status = service.get_active_scenario(current_date)
    ollama_stat = OllamaManager.check_status(settings.OLLAMA_HOST, settings.OLLAMA_MODEL)
    mode = service.get_mode()
    
    return {
        "active_scenario": status,
        "ollama_status": ollama_stat,
        "mode": mode
    }

@router.post("/mode")
def set_scenario_mode(mode: str = Query(..., description="Mode to set: AUTO | SIMULATED | NEWS")):
    if mode not in ['AUTO', 'SIMULATED', 'NEWS']:
        raise HTTPException(status_code=400, detail="Invalid mode value. Use AUTO, SIMULATED, or NEWS.")
    service.set_mode(mode)
    return {"status": "success", "message": f"Operational mode switched to {mode}"}

@router.post("/simulate")
def set_scenario_simulation(
    event: str = Body(..., embed=True),
    region: str = Body(..., embed=True),
    area: str = Body(..., embed=True),
    severity: str = Body(..., embed=True)
):
    if not event or not region or not area or not severity:
        raise HTTPException(status_code=400, detail="All fields (event, region, area, severity) are required.")
    service.set_simulation(event, region, area, severity)
    return {"status": "success", "message": f"Simulation set for {event} in {area}, {region} ({severity} severity)"}

@router.post("/reset")
def reset_scenario_simulation():
    service.reset_simulation()
    return {"status": "success", "message": "Simulation cleared. Reverted to time-based auto-detection."}

@router.get("/news")
def get_live_news():
    try:
        headlines = service.fetch_live_news()
        return headlines
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch news: {str(e)}")

@router.post("/news-extract")
def extract_scenario_from_news(db: Session = Depends(get_db)):
    try:
        extracted = service.extract_scenario_from_news(db)
        return extracted
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract news scenario: {str(e)}")

@router.post("/analyze")
def run_scenario_analysis(date_str: str = Query(..., description="Evaluation date YYYY-MM-DD"), db: Session = Depends(get_db)):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    try:
        results = service.run_analysis(db, current_date)
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/commit")
def commit_scenario_recommendations(db: Session = Depends(get_db)):
    try:
        result = service.commit_recommendations(db)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Commit failed: {str(e)}")

@router.get("/ollama-status")
def get_ollama_status():
    return OllamaManager.check_status(settings.OLLAMA_HOST, settings.OLLAMA_MODEL)

@router.post("/ollama-pull")
def pull_ollama_model():
    OllamaManager.start_pull(settings.OLLAMA_HOST, settings.OLLAMA_MODEL)
    return {"status": "success", "message": f"Started pulling model {settings.OLLAMA_MODEL} in background thread."}
