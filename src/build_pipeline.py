"""One-shot pipeline builder: load → clean → embed → index.

Run: python -m src.build_pipeline [--source auto|foodcom|recipe1m]
Env options: MAX_RECIPES=10000, EMBEDDING_BATCH_SIZE=128
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from loguru import logger

from src.ingestion.load_data import load_dataset
from src.preprocessing.clean_text import clean_recipe_dataframe
from src.preprocessing.ingredient_parser import normalise_ingredient_list
from src.embedding.embedder import RecipeEmbedder
from src.embedding.vector_store import RecipeVectorStore
from src.utils.config import settings


def build_pipeline(source: str = "auto") -> None:
    """Execute the full data → embedding → index build pipeline."""
    total_start = time.perf_counter()

    # Phase 1: Load data
    logger.info("═══ Phase 1: Data Loading ═══")
    df = load_dataset(source=source)
    logger.info(f"Loaded {len(df):,} raw recipes.")

    # Phase 2: Clean and filter
    logger.info("═══ Phase 2: Preprocessing ═══")
    df = clean_recipe_dataframe(df)

    cfg = settings.preprocessing
    df["_n_ings"] = df["ingredients"].apply(lambda x: len(x) if isinstance(x, list) else 0)
    before = len(df)
    df = df[
        (df["_n_ings"] >= cfg.min_ingredients)
        & (df["_n_ings"] <= cfg.max_ingredients)
    ].drop(columns=["_n_ings"]).reset_index(drop=True)
    logger.info(
        f"After ingredient filter ({cfg.min_ingredients}–{cfg.max_ingredients}): "
        f"{len(df):,} recipes (dropped {before - len(df):,})."
    )

    processed_path = settings.paths.processed_data / "recipes_clean.parquet"
    df.to_parquet(processed_path, index=False)
    logger.info(f"Processed data saved → {processed_path}")

    # Phase 3: Generate embeddings
    logger.info("═══ Phase 3: Embedding Generation ═══")
    embedder = RecipeEmbedder()
    vectors = embedder.encode_recipes(df, show_progress=True)

    # Phase 4: Build and save FAISS index
    logger.info("═══ Phase 4: FAISS Index Build ═══")
    store = RecipeVectorStore()
    store.build(vectors, df)
    store.save()

    elapsed = round(time.perf_counter() - total_start, 1)
    logger.info(f"═══ Pipeline complete in {elapsed}s. Indexed {store.size:,} recipes. ═══")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Recipe GenAI pipeline.")
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "foodcom", "recipe1m"],
        help="Dataset source to use.",
    )
    args = parser.parse_args()
    build_pipeline(source=args.source)
