"""
src/build_pipeline.py
────────────────────────────────────────────────────────
One-shot pipeline builder.

Run this script ONCE to:
  1. Load the raw recipe dataset
  2. Clean and preprocess recipes
  3. Generate sentence-transformer embeddings
  4. Build and save the FAISS vector index

Usage
─────
    python -m src.build_pipeline

Options (via env vars)
──────────────────────
    MAX_RECIPES=10000   limit recipes loaded (useful for testing)
    EMBEDDING_BATCH_SIZE=128   embedding batch size
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
    """
    Execute the full data → embedding → index build pipeline.

    Parameters
    ----------
    source : str
        Dataset source: "auto", "foodcom", or "recipe1m".
    """
    total_start = time.perf_counter()

    # ── Phase 1: Data loading ─────────────────────────────
    logger.info("═══ Phase 1: Data Loading ═══")
    df = load_dataset(source=source)
    logger.info(f"Loaded {len(df):,} raw recipes.")

    # ── Phase 2: Cleaning ─────────────────────────────────
    logger.info("═══ Phase 2: Preprocessing ═══")
    df = clean_recipe_dataframe(df)

    # Filter by ingredient count
    cfg = settings.preprocessing
    df["_n_ings"] = df["ingredients"].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )
    before = len(df)
    df = df[
        (df["_n_ings"] >= cfg.min_ingredients)
        & (df["_n_ings"] <= cfg.max_ingredients)
    ].drop(columns=["_n_ings"]).reset_index(drop=True)
    logger.info(
        f"After ingredient count filter ({cfg.min_ingredients}–{cfg.max_ingredients}): "
        f"{len(df):,} recipes (dropped {before - len(df):,})."
    )

    # ── Save processed data ───────────────────────────────
    processed_path = settings.paths.processed_data / "recipes_clean.parquet"
    df.to_parquet(processed_path, index=False)
    logger.info(f"Processed data saved → {processed_path}")

    # ── Phase 3: Embeddings ───────────────────────────────
    logger.info("═══ Phase 3: Embedding Generation ═══")
    embedder = RecipeEmbedder()
    vectors = embedder.encode_recipes(df, show_progress=True)

    # ── Phase 4: Vector Store ─────────────────────────────
    logger.info("═══ Phase 4: FAISS Index Build ═══")
    store = RecipeVectorStore()
    store.build(vectors, df)
    store.save()

    elapsed = round(time.perf_counter() - total_start, 1)
    logger.info(
        f"═══ Pipeline complete in {elapsed}s. "
        f"Indexed {store.size:,} recipes. ═══"
    )


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
