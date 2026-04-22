"""
src/embedding/vector_store.py
────────────────────────────────────────────────────────
FAISS-backed vector store for recipe embeddings.

Features
────────
• Build a new index from scratch and persist to disk.
• Load an existing index + metadata from disk.
• Perform top-k similarity search.
• Supports two index types:
    "flat"  – IndexFlatIP (exact inner-product / cosine, small datasets)
    "ivf"   – IndexIVFFlat (approximate, faster for >100k recipes)

Usage
─────
    from src.embedding.vector_store import RecipeVectorStore

    store = RecipeVectorStore()
    store.build(vectors, df)          # build from scratch
    store.save()                      # persist to disk

    store2 = RecipeVectorStore()
    store2.load()                     # restore from disk
    results = store2.search(query_vec, top_k=5)
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
import pandas as pd
from loguru import logger

from src.utils.config import settings


class RecipeVectorStore:
    """
    Manages the FAISS index and associated recipe metadata.

    Attributes
    ----------
    index : faiss.Index
    metadata : pd.DataFrame   (aligned with FAISS index order)
    """

    def __init__(
        self,
        index_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
    ) -> None:
        self.index_path = index_path or settings.paths.faiss_index
        self.metadata_path = (
            metadata_path
            or settings.paths.faiss_index.with_suffix(".meta.pkl")
        )
        self.index: Optional[faiss.Index] = None
        self.metadata: Optional[pd.DataFrame] = None

    # ── Build ─────────────────────────────────────────────

    def build(
        self,
        vectors: np.ndarray,
        metadata: pd.DataFrame,
    ) -> None:
        """
        Build the FAISS index from recipe embedding vectors.

        Parameters
        ----------
        vectors  : np.ndarray  shape (N, dim), dtype float32
                   Should already be L2-normalised (from embedder).
        metadata : pd.DataFrame  rows aligned with vectors
        """
        n, dim = vectors.shape
        index_type = settings.retrieval.index_type

        logger.info(
            f"Building FAISS index ({index_type}) for {n:,} vectors of dim {dim}."
        )

        if index_type == "ivf":
            nlist = settings.retrieval.nlist
            quantiser = faiss.IndexFlatIP(dim)
            self.index = faiss.IndexIVFFlat(quantiser, dim, nlist, faiss.METRIC_INNER_PRODUCT)
            logger.info(f"Training IVF index with nlist={nlist}…")
            self.index.train(vectors)
        else:
            # Default: exact inner-product (cosine, since vectors are normalised)
            self.index = faiss.IndexFlatIP(dim)

        self.index.add(vectors)
        self.metadata = metadata.reset_index(drop=True)

        logger.info(f"FAISS index built. Total vectors: {self.index.ntotal:,}")

    # ── Persist ───────────────────────────────────────────

    def save(self) -> None:
        """Write the index and metadata to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)
        logger.info(f"Index saved to {self.index_path}")
        logger.info(f"Metadata saved to {self.metadata_path}")

    # ── Load ──────────────────────────────────────────────

    def load(self) -> None:
        """Load the index and metadata from disk."""
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {self.index_path}. "
                "Run the build pipeline first."
            )
        self.index = faiss.read_index(str(self.index_path))
        with open(self.metadata_path, "rb") as f:
            self.metadata = pickle.load(f)
        logger.info(
            f"Loaded FAISS index ({self.index.ntotal:,} vectors) "
            f"and {len(self.metadata):,} metadata rows."
        )

    # ── Search ────────────────────────────────────────────

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Retrieve the top-k most similar recipes for a query vector.

        Parameters
        ----------
        query_vector : np.ndarray  shape (1, dim) or (dim,), float32
        top_k        : int  (defaults to config value)

        Returns
        -------
        list[dict]  each dict has keys: id, title, ingredients,
                    instructions, tags, similarity_score
        """
        if self.index is None or self.metadata is None:
            raise RuntimeError("Vector store is not loaded. Call build() or load() first.")

        top_k = top_k or settings.retrieval.top_k
        query_vector = query_vector.astype(np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector[np.newaxis, :]

        scores, indices = self.index.search(query_vector, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue  # FAISS padding for IVF
            if score < settings.retrieval.score_threshold:
                continue
            row = self.metadata.iloc[idx].to_dict()
            row["similarity_score"] = round(float(score), 4)
            results.append(row)

        return results

    # ── Incremental update ────────────────────────────────

    def add_recipes(
        self,
        new_vectors: np.ndarray,
        new_metadata: pd.DataFrame,
    ) -> None:
        """
        Add new recipe vectors to an existing index without rebuilding.

        Parameters
        ----------
        new_vectors  : np.ndarray  (M, dim) float32, L2-normalised
        new_metadata : pd.DataFrame  rows aligned with new_vectors
        """
        if self.index is None:
            raise RuntimeError("Index must be built or loaded before adding vectors.")
        self.index.add(new_vectors)
        self.metadata = pd.concat(
            [self.metadata, new_metadata], ignore_index=True
        )
        logger.info(
            f"Added {len(new_vectors)} vectors. "
            f"Total: {self.index.ntotal:,}"
        )

    @property
    def size(self) -> int:
        """Number of vectors stored in the index."""
        return self.index.ntotal if self.index else 0
