"""
FastAPI Application — Agent Gateway entry point.

Run with:
    uvicorn src.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import settings
from src.observability.langfuse_setup import get_langfuse_client, init_langfuse
from src.services.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_langfuse()
    yield
    client = get_langfuse_client()
    if client:
        client.flush()


app = FastAPI(
    title="E-Commerce Support Agent",
    description="LangGraph ReAct agent for e-commerce customer support",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host=settings.api_host, port=settings.api_port, reload=True)
