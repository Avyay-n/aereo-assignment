from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes import router
from app.config import APP_NAME, APP_VERSION, DESCRIPTION
from app.services.storage import StorageService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    StorageService.init_db()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for cross-origin frontend or GIS client integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints
app.include_router(router)


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serves the interactive web measurement dashboard."""
    from fastapi.responses import HTMLResponse
    from pathlib import Path

    index_file = Path(__file__).resolve().parent / "static" / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
