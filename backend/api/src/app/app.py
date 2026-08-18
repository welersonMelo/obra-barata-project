"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI

from app.controllers.ifc_controller import router as ifc_router
from app.controllers.pricing_controller import router as pricing_router
from app.controllers.project_controller import router as project_router
from app.database import initialize_database
from app.settings import get_settings


settings = get_settings()
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("app").setLevel(log_level)

app = FastAPI(
    title="Obra Barata API",
    root_path=settings.ROOT_PATH_BACKEND,
)
app.include_router(project_router)
app.include_router(ifc_router)
app.include_router(pricing_router)


@app.on_event("startup")
def startup() -> None:
    """Prepare runtime dependencies."""

    initialize_database()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Simple health check."""

    return {"status": "ok"}


def main() -> None:
    """Run the API with Uvicorn for local execution."""

    import uvicorn

    uvicorn.run("app.app:app", host="0.0.0.0", port=8000, reload=False)
