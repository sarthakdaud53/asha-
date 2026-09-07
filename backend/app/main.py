import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.db.database import engine, Base, SessionLocal
from backend.app.db.migrations import run_migrations
from backend.app.db.seed import seed_database
from backend.app.db.location_import import import_lgd_snapshot
from backend.app.api.routers import (
    auth,
    children,
    vaccines,
    immunizations,
    growth,
    asha,
    admin,
    notifications
    , locations
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown events:
    Initializes database tables and seeds standard UIP vaccines & demo data.
    """
    print("[STARTUP] Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    print("[STARTUP] Checking for schema drift on existing tables...")
    run_migrations(engine)

    print("[STARTUP] Checking and seeding database...")
    seed_database()
    location_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "lgd", "village-directory.csv"))
    print("[STARTUP] Loading LGD location hierarchy...")
    location_db = SessionLocal()
    try:
        print(f"[LOCATION] {import_lgd_snapshot(location_db, Path(location_file))}")
    finally:
        location_db.close()
    
    yield
    print("[SHUTDOWN] Application shutting down.")

app = FastAPI(
    title=settings.APP_NAME,
    description="Rural Child Health & Universal Immunization Programme Management System designed for Parents, ASHA Workers, and Health Administrators.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

# Include API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(children.router, prefix="/api")
app.include_router(vaccines.router, prefix="/api")
app.include_router(immunizations.router, prefix="/api")
app.include_router(growth.router, prefix="/api")
app.include_router(asha.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(locations.router, prefix="/api")

# Static frontend assets mount
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    # Mount subdirectories if they exist
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    assets_dir = os.path.join(frontend_dir, "assets")
    
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Serve main HTML pages
    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/parent", include_in_schema=False)
    @app.get("/parent.html", include_in_schema=False)
    async def serve_parent():
        return FileResponse(os.path.join(frontend_dir, "parent.html"))

    @app.get("/asha", include_in_schema=False)
    @app.get("/asha.html", include_in_schema=False)
    async def serve_asha():
        return FileResponse(os.path.join(frontend_dir, "asha.html"))

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin.html", include_in_schema=False)
    async def serve_admin():
        return FileResponse(os.path.join(frontend_dir, "admin.html"))

@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV
    }
