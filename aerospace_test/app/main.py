import os
from core.config import settings
from fastapi import FastAPI
from core import endpoints
from fastapi.middleware.cors import CORSMiddleware


token_length = os.getenv('TOKEN_BYTES_LENGTH', 8)
geojson_hours_alive = os.getenv('GEOJSON_HOURS_ALIVE', 24)


def get_application():
    _app = FastAPI(title=settings.PROJECT_NAME)
    _app.include_router(endpoints.router)

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin)
                       for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return _app


app = get_application()
