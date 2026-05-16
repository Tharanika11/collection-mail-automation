from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.collection_routes import router as collection_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Collections Email Automation API",
        description="Backend API for collection reminder eligibility, reply handling, and email preparation.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(collection_router)
    return app


app = create_app()
