"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wss_common.config import settings

from app.bootstrap import bootstrap
from app.routers import (
    auth,
    batches,
    dashboard,
    geojson,
    georeference,
    health,
    jobs,
    maps,
    operators,
    review,
    targets,
    uploads,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(maps.router, prefix="/api/maps", tags=["maps"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(operators.router, prefix="/api/operators", tags=["operators"])
app.include_router(targets.router, prefix="/api/targets", tags=["targets"])
app.include_router(batches.router, prefix="/api/batches", tags=["batches"])
app.include_router(geojson.router, prefix="/api/geojson", tags=["geojson"])
app.include_router(georeference.router, prefix="/api/georeference", tags=["georeference"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
