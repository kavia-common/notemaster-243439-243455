from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.db import create_db_engine
from src.api.routes import build_router

openapi_tags = [
    {"name": "meta", "description": "Health and metadata endpoints."},
    {"name": "notes", "description": "Create, update, delete, list, and search notes."},
    {"name": "tags", "description": "Tag listing and management."},
]

app = FastAPI(
    title="NoteMaster API",
    description="REST API for a fullstack notes application (notes, tags, search, pin/favorite).",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = create_db_engine()
app.include_router(build_router(_engine))


@app.get(
    "/",
    tags=["meta"],
    summary="Health check",
    description="Basic health check endpoint.",
    operation_id="health_check",
)
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint used by platform liveness probes."""
    return {"message": "Healthy"}
