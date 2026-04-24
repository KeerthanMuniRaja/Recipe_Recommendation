"""
src/utils/config.py
────────────────────────────────────────────────────────
Central configuration for the Recipe GenAI System.
All runtime settings are read from environment variables
(with sensible defaults) so they can be overridden via
a .env file or Docker / k8s secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=True)


# ─────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────
@dataclass
class PathConfig:
    base_dir: Path = BASE_DIR
    raw_data: Path = BASE_DIR / "data" / "raw"
    processed_data: Path = BASE_DIR / "data" / "processed"
    models_dir: Path = BASE_DIR / "models" / "embeddings"
    faiss_index: Path = BASE_DIR / "models" / "embeddings" / "recipes.index"
    recipe_metadata: Path = BASE_DIR / "data" / "processed" / "recipes_meta.parquet"

    def __post_init__(self):
        for p in [self.raw_data, self.processed_data, self.models_dir]:
            p.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────
# Embedding
# ─────────────────────────────────────────────────────────
@dataclass
class EmbeddingConfig:
    # Model used for generating recipe / ingredient embeddings
    model_name: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    # Dimension of the embedding vectors (must match model output)
    vector_dim: int = int(os.getenv("VECTOR_DIM", "384"))
    # Batch size when encoding large recipe corpora
    batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    # Maximum token length fed to the encoder
    max_seq_length: int = int(os.getenv("MAX_SEQ_LENGTH", "256"))


# ─────────────────────────────────────────────────────────
# FAISS / Retrieval
# ─────────────────────────────────────────────────────────
@dataclass
class RetrievalConfig:
    # Number of top recipes to retrieve per query
    top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    # FAISS index type: "flat" (exact), "ivf" (approximate, faster for large sets)
    index_type: str = os.getenv("FAISS_INDEX_TYPE", "flat")
    # IVF nlist — only used when index_type == "ivf"
    nlist: int = int(os.getenv("FAISS_NLIST", "100"))
    # Minimum cosine similarity to include a result (0–1)
    score_threshold: float = float(os.getenv("SCORE_THRESHOLD", "0.2"))


# ─────────────────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────────────────
@dataclass
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "openai")   # "openai" | "anthropic" | "groq"
    model_name: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    @property
    def api_key(self) -> str:
        if self.provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY", "")
        elif self.provider == "groq":
            return os.getenv("GROQ_API_KEY", "")
        return os.getenv("OPENAI_API_KEY", "")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    # How many retrieved recipes to include in the RAG context
    context_recipes: int = int(os.getenv("LLM_CONTEXT_RECIPES", "3"))


# ─────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────
@dataclass
class APIConfig:
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    workers: int = int(os.getenv("API_WORKERS", "2"))
    reload: bool = os.getenv("API_RELOAD", "false").lower() == "true"
    log_level: str = os.getenv("API_LOG_LEVEL", "info")
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )


# ─────────────────────────────────────────────────────────
# Preprocessing
# ─────────────────────────────────────────────────────────
@dataclass
class PreprocessingConfig:
    # Drop recipes with fewer than this many ingredients
    min_ingredients: int = int(os.getenv("MIN_INGREDIENTS", "2"))
    # Drop recipes with more than this many ingredients (outliers)
    max_ingredients: int = int(os.getenv("MAX_INGREDIENTS", "30"))
    # Maximum number of recipes to load (None = all)
    max_recipes: int | None = (
        int(os.getenv("MAX_RECIPES")) if os.getenv("MAX_RECIPES") else None
    )


# ─────────────────────────────────────────────────────────
# Master Settings (singleton-style access)
# ─────────────────────────────────────────────────────────
@dataclass
class Settings:
    paths: PathConfig = field(default_factory=PathConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    api: APIConfig = field(default_factory=APIConfig)
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)


# Module-level singleton – import this everywhere
settings = Settings()
