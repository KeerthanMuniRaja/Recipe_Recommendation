"""Generates dense vector embeddings for recipes and queries using SentenceTransformers."""

from __future__ import annotations

from typing import Union
import numpy as np
import pandas as pd
from loguru import logger
from sentence_transformers import SentenceTransformer

from src.utils.config import settings
from src.preprocessing.ingredient_parser import normalise_ingredient_list


class RecipeEmbedder:
    """Thin wrapper around a SentenceTransformer model."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding.model_name
        logger.info(f"Loading embedding model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)
        self._model.max_seq_length = settings.embedding.max_seq_length
        logger.info("Embedding model loaded.")

    @staticmethod
    def _recipe_to_text(row: pd.Series) -> str:
        """Convert a recipe row to an embeddable text string: '<title> | ingredients: <ing1>, ...'"""
        title = str(row.get("clean_title") or row.get("title", ""))
        ingredients = row.get("ingredients", [])
        if isinstance(ingredients, list):
            normed = normalise_ingredient_list(ingredients)
        else:
            normed = [str(ingredients)]
        ingredient_text = ", ".join(normed)
        return f"{title} | ingredients: {ingredient_text}"

    def encode_recipes(
        self,
        df: pd.DataFrame,
        batch_size: int | None = None,
        show_progress: bool = True,
    ) -> np.ndarray:
        """Encode all recipes in a DataFrame into embedding vectors. Returns shape (N, dim) float32."""
        batch_size = batch_size or settings.embedding.batch_size
        logger.info(f"Encoding {len(df):,} recipes in batches of {batch_size}…")

        texts = [self._recipe_to_text(row) for _, row in df.iterrows()]

        vectors = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,  # enables cosine similarity via dot product
        )
        logger.info(f"Encoded. Matrix shape: {vectors.shape}")
        return vectors.astype(np.float32)

    def encode_query(
        self,
        ingredients: list[str],
        extra_context: str = "",
    ) -> np.ndarray:
        """Encode a user ingredient list into a query vector. Returns shape (1, dim) float32."""
        normed = normalise_ingredient_list(ingredients)
        ingredient_text = ", ".join(normed)
        if extra_context:
            query_text = f"{extra_context} | ingredients: {ingredient_text}"
        else:
            query_text = f"ingredients: {ingredient_text}"

        vector = self._model.encode(
            [query_text],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vector.astype(np.float32)

    @property
    def vector_dim(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._model.get_sentence_embedding_dimension()
