"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.controllers.ifc_controller import router as ifc_router
from app.settings import get_settings


settings = get_settings()

app = FastAPI(
    title="Obra Barata API",
    root_path=settings.ROOT_PATH_BACKEND,
)
app.include_router(ifc_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Simple health check."""

    return {"status": "ok"}


def main() -> None:
    """Run the API with Uvicorn for local execution."""

    import uvicorn

    uvicorn.run("app.app:app", host="0.0.0.0", port=8000, reload=False)
