"""
src/api/app.py
────────────────────────────────────────────────────────
FastAPI application for the Recipe GenAI System.

Endpoints
─────────
POST /api/v1/recommend        – main RAG-powered recommendation
POST /api/v1/substitutions    – ingredient substitution lookup
GET  /api/v1/health           – health check
GET  /api/v1/store/info       – vector store stats
POST /api/v1/search/quick     – fast retrieval without LLM

Run locally
───────────
    uvicorn src.api.app:app --reload --port 8000
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from src.rag.rag_pipeline import RAGPipeline
from src.retrieval.retriever import RecipeRetriever
from src.utils.config import settings


# ─────────────────────────────────────────────────────────
# Application state (shared singletons)
# ─────────────────────────────────────────────────────────

class AppState:
    pipeline: RAGPipeline | None = None
    retriever: RecipeRetriever | None = None


app_state = AppState()


# ─────────────────────────────────────────────────────────
# Startup / shutdown lifecycle
# ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy models once at startup, release at shutdown."""
    logger.info("🚀 Starting Recipe GenAI API…")

    # Initialise shared retriever (loads FAISS index + embedding model)
    app_state.retriever = RecipeRetriever()
    app_state.retriever.load()

    # Initialise RAG pipeline with the shared retriever
    app_state.pipeline = RAGPipeline(retriever=app_state.retriever)
    app_state.pipeline._ensure_loaded()

    logger.info("✅ API ready.")
    yield

    logger.info("Shutting down Recipe GenAI API…")


# ─────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────

app = FastAPI(
    title="Recipe GenAI System",
    description=(
        "RAG-powered recipe recommendation API. "
        "Submit your available ingredients and get personalised, "
        "step-by-step cooking instructions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    ingredients: list[str] = Field(
        ...,
        min_length=1,
        max_length=30,
        description="List of available ingredients (raw names, quantities optional).",
        examples=[["eggs", "flour", "butter", "sugar", "milk"]],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of recipe candidates to retrieve.",
    )
    context: Optional[str] = Field(
        default="",
        max_length=200,
        description="Optional free-text hint (cuisine type, dietary restriction, etc.)",
        examples=["Italian, low-carb"],
    )
    include_nutrition: bool = Field(
        default=False,
        description="Include a nutritional estimate in the response.",
    )

    @field_validator("ingredients")
    @classmethod
    def validate_ingredients(cls, v):
        cleaned = [i.strip() for i in v if i.strip()]
        if not cleaned:
            raise ValueError("ingredients list must not be empty after stripping whitespace.")
        return cleaned


class SubstitutionRequest(BaseModel):
    recipe_title: str = Field(..., max_length=200)
    missing_ingredients: list[str] = Field(..., min_length=1, max_length=20)


class QuickSearchRequest(BaseModel):
    ingredients: list[str] = Field(..., min_length=1, max_length=30)
    top_k: int = Field(default=5, ge=1, le=20)
    context: Optional[str] = Field(default="")


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=1000)
    context: Optional[str] = Field(default="")


# ─────────────────────────────────────────────────────────
# Middleware: request timing
# ─────────────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(elapsed)
    return response


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict:
    """
    Health check endpoint.
    Returns API status and vector store size.
    """
    store_size = app_state.retriever.store_size if app_state.retriever else 0
    return {
        "status": "ok",
        "api_version": "1.0.0",
        "vector_store_recipes": store_size,
        "llm_provider": settings.llm.provider,
        "embedding_model": settings.embedding.model_name,
    }


@app.get("/api/v1/store/info", tags=["System"])
async def store_info() -> dict:
    """Return metadata about the loaded vector store."""
    if not app_state.retriever:
        raise HTTPException(status_code=503, detail="Retriever not initialised.")
    return {
        "total_recipes_indexed": app_state.retriever.store_size,
        "embedding_model": settings.embedding.model_name,
        "vector_dim": settings.embedding.vector_dim,
        "index_type": settings.retrieval.index_type,
        "top_k_default": settings.retrieval.top_k,
    }


@app.post(
    "/api/v1/recommend",
    tags=["Recipes"],
    summary="Get AI-powered recipe recommendations",
    response_description="Best recipe with step-by-step instructions and substitutions.",
)
async def recommend_recipe(body: RecommendRequest) -> dict[str, Any]:
    """
    **Main endpoint.**

    Accepts a list of available ingredients and returns:
    - Best matching recipe (LLM-refined)
    - Step-by-step cooking instructions
    - Missing ingredients
    - Ingredient substitutions
    - All candidate recipes with similarity scores
    - Optional nutritional estimate
    """
    if not app_state.pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")

    try:
        result = await app_state.pipeline.run(
            ingredients=body.ingredients,
            top_k=body.top_k,
            context=body.context or "",
            include_nutrition=body.include_nutrition,
        )
    except Exception as exc:
        logger.exception("Error in recommend_recipe")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {str(exc)}",
        ) from exc

    return result


@app.post(
    "/api/v1/substitutions",
    tags=["Recipes"],
    summary="Get ingredient substitutions",
)
async def get_substitutions(body: SubstitutionRequest) -> dict[str, Any]:
    """
    Returns ingredient substitutions for missing items.
    Combines static lookup table + optional LLM refinement.
    """
    if not app_state.pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")

    try:
        subs = await app_state.pipeline.get_substitutions_only(
            recipe_title=body.recipe_title,
            missing_ingredients=body.missing_ingredients,
        )
    except Exception as exc:
        logger.exception("Error in get_substitutions")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "recipe": body.recipe_title,
        "substitutions": subs,
    }


@app.post(
    "/api/v1/search/quick",
    tags=["Recipes"],
    summary="Fast recipe search without LLM (retrieval only)",
)
async def quick_search(body: QuickSearchRequest) -> dict[str, Any]:
    """
    Performs only the FAISS similarity search.
    Much faster than /recommend — no LLM call.
    Returns raw candidates with similarity scores.
    """
    if not app_state.retriever:
        raise HTTPException(status_code=503, detail="Retriever not initialised.")

    try:
        candidates = app_state.retriever.retrieve(
            ingredients=body.ingredients,
            top_k=body.top_k,
            context=body.context or "",
        )
    except Exception as exc:
        logger.exception("Error in quick_search")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ingredients": body.ingredients,
        "total_found": len(candidates),
        "recipes": [c.to_dict() for c in candidates],
    }


@app.post(
    "/api/v1/chat",
    tags=["Chat"],
    summary="Interactive AI Chat",
)
async def chat_interaction(body: ChatRequest) -> dict[str, Any]:
    """
    Answers free-form questions from the user using the configured LLM.
    """
    if not app_state.pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")
    
    try:
        system_prompt = (
            "You are a helpful culinary AI assistant. "
            "Answer the user's question concisely. "
        )
        if body.context:
            system_prompt += f"\nContext provided by the user's current view:\n{body.context}"
            
        response = await app_state.pipeline._llm.chat(
            system=system_prompt,
            user=body.message
        )
    except Exception as exc:
        logger.exception("Error in chat_interaction")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
        
    return {"reply": response}


# ─────────────────────────────────────────────────────────
# Global exception handler
# ─────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred.", "path": str(request.url.path)},
    )


# ─────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.app:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=settings.api.workers,
        log_level=settings.api.log_level,
    )
