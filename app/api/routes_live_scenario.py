from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from datetime import date
from app.core.database import get_db
from app.services.live_scenario_service import LiveScenarioService, OllamaManager

router = APIRouter(prefix="/live-scenario", tags=["Live AI Scenario Analysis"])
service = LiveScenarioService()

@router.get("/status")
def get_scenario_status(date_str: str = Query(..., description="Evaluation date YYYY-MM-DD"), db: Session = Depends(get_db)):
    try:
        current_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    status = service.get_active_scenario(current_date)
    llm_stat = OllamaManager.check_status()
    mode = service.get_mode()
    
    return {
        "active_scenario": status,
        "ollama_status": llm_stat,
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

@router.get("/llm-status")
def get_llm_status():
    return OllamaManager.check_status()

@router.get("/ollama-status")
def get_ollama_status():
    """Frontend-facing alias for /llm-status — reports Ollama Cloud connectivity."""
    return OllamaManager.check_status()

@router.post("/ollama-pull")
def pull_ollama_model():
    """
    For local Ollama, this would pull a model. For Ollama Cloud,
    models are always available server-side — just confirm the key is set.
    """
    status = OllamaManager.check_status()
    if status["is_connected"]:
        return {
            "status": "success",
            "message": f"Ollama Cloud is ready. Model '{status['model']}' is available on Ollama Cloud servers.",
            "is_cloud": True
        }
    else:
        return {
            "status": "error",
            "message": "OLLAMA_API_KEY is not set. Add it to your .env file.",
            "is_cloud": True
        }
