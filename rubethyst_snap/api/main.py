from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .cors_util import effective_cors_origins
from .routes import router
from .settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Rubethyst Snap",
        version="0.1.0",
        description="Rubethyst Lab's video download SaaS API.",
    )
    cors = effective_cors_origins(settings)
    if cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    """Console entrypoint used by ``rubethyst-snap-api``."""

    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "rubethyst_snap.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
