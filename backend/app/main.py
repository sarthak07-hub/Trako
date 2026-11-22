import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import Base, engine
import app.models  # Ensures all models are registered

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="Smart Bus Transportation and Management Platform for Passengers, Operators, Drivers, and Conductors",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
from app.routers import auth, passenger, operator, driver, conductor, tracking, qr

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(passenger.router, prefix=settings.API_V1_PREFIX)
app.include_router(operator.router, prefix=settings.API_V1_PREFIX)
app.include_router(driver.router, prefix=settings.API_V1_PREFIX)
app.include_router(conductor.router, prefix=settings.API_V1_PREFIX)
app.include_router(tracking.router, prefix=settings.API_V1_PREFIX)
app.include_router(qr.router, prefix=settings.API_V1_PREFIX)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "tagline": settings.TAGLINE,
        "version": "1.0.0"
    }

# Frontend static files mounting
# Locate frontend folder relative to backend directory
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

if os.path.exists(frontend_dir):
    # Mount css, js, assets, and pages
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
    app.mount("/pages", StaticFiles(directory=os.path.join(frontend_dir, "pages")), name="pages")
    if os.path.exists(os.path.join(frontend_dir, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

@app.get("/")
def root():
    return RedirectResponse(url="/pages/index.html")
