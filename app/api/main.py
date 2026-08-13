from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import time
from app.core.config import settings
from app.core.logging_config import logger
from app.api import routes_dashboard, routes_forecast, routes_inventory, routes_recommendations
from app.core.database import engine
from app.models.database_models import Base

# Setup tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Production-Grade Demand Sensing & Replenishment Planning API for MedCare Pharma",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom execution timer middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"Endpoint {request.url.path} served in {process_time:.4f}s")
    return response

# Global error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception caught on path {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details.", "error": str(exc)}
    )

# Include routers
app.include_router(routes_dashboard.router, prefix=settings.API_V1_STR)
app.include_router(routes_forecast.router, prefix=settings.API_V1_STR)
app.include_router(routes_inventory.router, prefix=settings.API_V1_STR)
app.include_router(routes_recommendations.router, prefix=settings.API_V1_STR)

# Mount dashboard static files
app.mount("/static", StaticFiles(directory="dashboard"), name="static")

@app.get("/")
def read_root():
    return FileResponse("dashboard/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
