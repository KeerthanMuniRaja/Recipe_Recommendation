"""FastAPI application for the Recipe GenAI System.

Endpoints:
    POST /api/v1/recommend       - RAG-powered recipe recommendation
    POST /api/v1/substitutions   - ingredient substitution lookup
    GET  /api/v1/health          - health check
    GET  /api/v1/store/info      - vector store stats
    POST /api/v1/search/quick    - fast retrieval without LLM
    POST /api/v1/chat            - free-form culinary AI chat
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from src.rag.rag_pipeline import RAGPipeline
from src.retrieval.retriever import RecipeRetriever
from src.utils.config import settings


class AppState:
    pipeline: RAGPipeline | None = None
    retriever: RecipeRetriever | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy models once at startup, release at shutdown."""
    logger.info("🚀 Starting Recipe GenAI API…")

    app_state.retriever = RecipeRetriever()
    app_state.retriever.load()

    app_state.pipeline = RAGPipeline(retriever=app_state.retriever)
    app_state.pipeline._ensure_loaded()

    logger.info("✅ API ready.")
    yield

    logger.info("Shutting down Recipe GenAI API…")


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


# Request / Response schemas

class RecommendRequest(BaseModel):
    ingredients: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
    context: Optional[str] = Field(default="")
    include_nutrition: bool = Field(default=False)
    image_base64: Optional[str] = Field(default=None)

    @field_validator("ingredients")
    @classmethod
    def validate_ingredients(cls, v):
        cleaned = [i.strip() for i in v if i.strip()]
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
    history: Optional[list[dict]] = Field(default=None)


# Middleware: track per-request processing time
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(elapsed)
    return response


# Endpoints

@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict:
    """Health check — returns API status and vector store size."""
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
    Agentic workflow: if an image is provided, extracts ingredients first using LangGraph.
    Then retrieves candidates and generates a final JSON recipe.
    """
    from src.agent.recipe_graph import recipe_agent

    if not body.ingredients and not body.image_base64:
        raise HTTPException(status_code=400, detail="Must provide ingredients or an image_base64.")

    try:
        initial_state = {
            "image_base64": body.image_base64,
            "ingredients": body.ingredients,
            "context": body.context or "",
            "top_k": body.top_k,
            "include_nutrition": body.include_nutrition,
            "vision_extracted_ingredients": [],
            "retrieved_candidates": [],
            "final_recipe": {},
            "error": None
        }

        result = await recipe_agent.ainvoke(initial_state)

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        final = result["final_recipe"]
        if result.get("vision_extracted_ingredients"):
            final["vision_ingredients"] = result["vision_extracted_ingredients"]

        return final

    except Exception as exc:
        logger.exception("Error in recommend_recipe")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {str(exc)}",
        ) from exc


@app.post("/api/v1/substitutions", tags=["Recipes"], summary="Get ingredient substitutions")
async def get_substitutions(body: SubstitutionRequest) -> dict[str, Any]:
    """Returns ingredient substitutions — combines static lookup + LLM refinement."""
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

    return {"recipe": body.recipe_title, "substitutions": subs}


@app.post(
    "/api/v1/search/quick",
    tags=["Recipes"],
    summary="Fast recipe search without LLM (retrieval only)",
)
async def quick_search(body: QuickSearchRequest) -> dict[str, Any]:
    """FAISS-only search — much faster than /recommend, no LLM call."""
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


@app.post("/api/v1/chat", tags=["Chat"], summary="Interactive AI Chat")
async def chat_interaction(body: ChatRequest) -> dict[str, Any]:
    """Answers free-form culinary questions using the configured LLM."""
    if not app_state.pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialised.")

    try:
        system_prompt = "You are a helpful culinary AI assistant. Answer the user's question concisely. "
        if body.context:
            system_prompt += f"\nContext provided by the user's current view:\n{body.context}"

        response = await app_state.pipeline._llm.chat(
            system=system_prompt,
            user=body.message,
            history=body.history
        )
    except Exception as exc:
        logger.exception("Error in chat_interaction")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"reply": response}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred.", "path": str(request.url.path)},
    )


# Serve React frontend from the built dist folder
frontend_dist = Path("frontend/dist")

if frontend_dist.is_dir():
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    for file in frontend_dist.iterdir():
        if file.is_file():
            @app.get(f"/{file.name}", tags=["Frontend"])
            async def serve_file(request: Request, f_path=file):
                return FileResponse(f_path)

    # Catch-all for SPA routing (must be last)
    @app.get("/{full_path:path}", tags=["Frontend"])
    async def serve_spa(request: Request, full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build not found")
else:
    logger.warning("Frontend dist directory not found. React app will not be served.")


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
